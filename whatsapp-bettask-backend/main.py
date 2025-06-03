"""
WhatsApp BetTask Backend - Main Application Entry Point

A self-accountability betting system powered by WhatsApp MCP, Supabase, and Gemini AI.
Users can create challenges, set financial stakes, submit proof via WhatsApp,
and get AI-powered verification.
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import uuid
import sqlite3
import json

from config.settings import settings
from api.whatsapp_mcp import whatsapp_mcp
from services.supabase_client import SupabaseClient
from utils.logger import setup_logger
from utils.error_handler import handle_error
from handlers.intent_router import IntentRouter
from handlers.fund_handler import FundHandler

# Initialize settings and logging
logger = setup_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="WhatsApp BetTask Backend",
    description="Self-accountability betting system via WhatsApp MCP",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [settings.SUPABASE_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
supabase_client = SupabaseClient()
intent_router = IntentRouter(supabase_client)

# Store last message check time for each user - make this persistent
user_last_check = {}

# Add global set to track processed messages - with timestamp-based cleanup
processed_messages = set()
LAST_PROCESSED_FILE = "last_processed_timestamp.txt"

def load_last_processed_time():
    """Load the last processed timestamp from file."""
    try:
        if os.path.exists(LAST_PROCESSED_FILE):
            with open(LAST_PROCESSED_FILE, 'r') as f:
                timestamp_str = f.read().strip()
                return datetime.fromisoformat(timestamp_str)
        else:
            # Default to current time to avoid processing old messages on first run
            return datetime.now()
    except Exception as e:
        logger.warning(f"Could not load last processed time: {e}")
        return datetime.now()

def save_last_processed_time(timestamp: datetime):
    """Save the last processed timestamp to file."""
    try:
        with open(LAST_PROCESSED_FILE, 'w') as f:
            f.write(timestamp.isoformat())
    except Exception as e:
        logger.error(f"Could not save last processed time: {e}")

# Global variable to track the last processed time
last_processed_time = load_last_processed_time()

@app.on_event("startup")
async def startup_event():
    """Initialize services on app startup."""
    global last_processed_time
    logger.info("Starting WhatsApp BetTask Backend with MCP integration...")
    
    # Log the last processed time
    logger.info(f"Last processed timestamp: {last_processed_time}")
    
    # Test database connection
    try:
        await supabase_client.health_check()
        logger.info("✅ Supabase connection established")
    except Exception as e:
        logger.error(f"❌ Supabase connection failed: {e}")
        raise

    # Check WhatsApp MCP bridge connection
    try:
        async with whatsapp_mcp as mcp:
            bridge_healthy = await mcp.check_bridge_health()
            if bridge_healthy:
                logger.info("✅ WhatsApp MCP bridge connected")
            else:
                logger.warning("⚠️ WhatsApp MCP bridge not responding")
    except Exception as e:
        logger.warning(f"⚠️ WhatsApp MCP bridge check failed: {e}")

    # Verify Gemini AI configuration
    if not settings.GEMINI_API_KEY:
        logger.warning("⚠️ Gemini API key not configured - AI features disabled")
    else:
        logger.info("✅ Gemini AI configured")

    # Start message polling task
    asyncio.create_task(poll_messages())
    
    logger.info("🚀 WhatsApp BetTask Backend ready with MCP integration!")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on app shutdown."""
    logger.info("Shutting down WhatsApp BetTask Backend...")

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "WhatsApp BetTask Backend",
        "status": "running",
        "version": "1.0.0",
        "integration": "WhatsApp MCP",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Detailed health check."""
    try:
        # Check Supabase connection
        supabase_healthy = await supabase_client.health_check()
        
        # Check WhatsApp MCP bridge
        mcp_healthy = False
        try:
            async with whatsapp_mcp as mcp:
                mcp_healthy = await mcp.check_bridge_health()
        except:
            pass
        
        return {
            "status": "healthy" if supabase_healthy and mcp_healthy else "partial",
            "services": {
                "supabase": "healthy" if supabase_healthy else "unhealthy",
                "whatsapp_mcp": "healthy" if mcp_healthy else "unhealthy",
                "gemini": "configured" if settings.GEMINI_API_KEY else "not_configured"
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

async def poll_messages():
    """
    Background task to poll for new WhatsApp messages.
    Only processes messages newer than the last processed timestamp.
    """
    global last_processed_time
    logger.info("Starting message polling task...")
    logger.info(f"Will only process messages newer than: {last_processed_time}")
    
    while True:
        try:
            # Get messages from MCP database that are newer than last processed time
            recent_messages = get_new_messages_from_db(last_processed_time)
            
            if recent_messages:
                logger.info(f"Found {len(recent_messages)} new messages to process")
                
                newest_timestamp = last_processed_time
                
                for message in recent_messages:
                    # Extract phone number from message
                    sender_phone = message.get("sender", "")
                    chat_jid = message.get("chat_jid", "")
                    message_timestamp_str = message.get("timestamp")
                    message_id = message.get("id", "")
                    
                    # Skip if no sender or timestamp
                    if not sender_phone or not message_timestamp_str:
                        continue
                    
                    # Parse timestamp
                    try:
                        message_timestamp = datetime.fromisoformat(message_timestamp_str.replace('+05:30', ''))
                    except:
                        logger.warning(f"Could not parse timestamp: {message_timestamp_str}")
                        continue
                    
                    # Skip if message is older than our cutoff
                    if message_timestamp <= last_processed_time:
                        continue
                    
                    # Create unique message key
                    message_key = f"{chat_jid}_{message_id}_{message_timestamp.isoformat()}"
                    
                    # Check if already processed
                    if message_key in processed_messages:
                        continue
                    
                    # Mark as processed
                    processed_messages.add(message_key)
                    
                    # Update newest timestamp
                    if message_timestamp > newest_timestamp:
                        newest_timestamp = message_timestamp
                    
                    # Try to find user in database or create temporary one
                    user_id = await get_or_create_user_for_phone(sender_phone)
                    
                    # Process the message
                    await process_message(user_id, sender_phone, message)
                
                # Update last processed time to the newest message we processed
                if newest_timestamp > last_processed_time:
                    last_processed_time = newest_timestamp
                    save_last_processed_time(last_processed_time)
                    logger.info(f"Updated last processed time to: {last_processed_time}")
            
            # Clean up old processed messages (keep last 1000)
            if len(processed_messages) > 1000:
                # Keep only the most recent entries (this is approximate but good enough)
                processed_messages.clear()
                logger.info("Cleared processed messages cache")
            
            # Wait before next poll
            await asyncio.sleep(10)  # Poll every 10 seconds
            
        except Exception as e:
            logger.error(f"Error in message polling: {e}")
            await asyncio.sleep(30)  # Wait longer on error

def get_new_messages_from_db(since_timestamp: datetime) -> list:
    """
    Get messages from the WhatsApp MCP database that are newer than the given timestamp.
    """
    try:
        # Path to the WhatsApp MCP database
        db_path = "/Users/dev16/Documents/Test project/dare-you-succeed-whatsapp-main/whatsapp-mcp/whatsapp-bridge/store/messages.db"
        
        if not os.path.exists(db_path):
            logger.warning(f"WhatsApp MCP database not found: {db_path}")
            return []
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # This enables column access by name
        cursor = conn.cursor()
        
        # Query for messages newer than the timestamp
        # Convert datetime to string for SQLite comparison
        timestamp_str = since_timestamp.strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("""
            SELECT id, chat_jid, sender, content, timestamp, is_from_me, 
                   media_type, filename, url
            FROM messages 
            WHERE timestamp > ? 
            AND is_from_me = 0
            AND (content IS NOT NULL OR media_type IS NOT NULL)
            ORDER BY timestamp ASC
            LIMIT 50
        """, (timestamp_str,))
        
        messages = []
        for row in cursor.fetchall():
            message = {
                "id": row["id"],
                "chat_jid": row["chat_jid"],
                "sender": row["sender"],
                "content": row["content"] or "",
                "timestamp": row["timestamp"],
                "is_from_me": bool(row["is_from_me"]),
                "media_type": row["media_type"],
                "filename": row["filename"],
                "url": row["url"]
            }
            messages.append(message)
            
            # Debug logging for message details
            logger.info(f"📨 Message from DB: ID={message['id'][:8]}..., "
                      f"sender={message['sender']}, content='{message['content'][:50]}...', "
                      f"media_type={message['media_type']}, timestamp={message['timestamp']}")
        
        conn.close()
        return messages
        
    except Exception as e:
        logger.error(f"Error querying WhatsApp MCP database: {e}")
        return []

async def get_or_create_user_for_phone(phone_number: str) -> str:
    """
    Get existing user ID for phone number or create a temporary one.
    This allows the system to respond to any WhatsApp number.
    """
    try:
        # Try to find existing user by phone number (column is 'phone' not 'phone_number')
        result = supabase_client.client.table("profiles").select("id").eq(
            "phone", phone_number
        ).execute()
        
        if result.data and len(result.data) > 0:
            user_id = result.data[0]["id"]
            logger.info(f"Found existing user {user_id} for phone {phone_number}")
            return user_id
        
        # If no user found, generate a proper UUID for temporary user
        temp_user_id = str(uuid.uuid4())
        logger.info(f"Using temporary user ID {temp_user_id} for phone {phone_number}")
        return temp_user_id
        
    except Exception as e:
        logger.error(f"Error getting user for phone {phone_number}: {e}")
        # Fallback to temporary UUID
        return str(uuid.uuid4())

async def process_message(user_id: str, phone_number: str, message: dict):
    """Process a new WhatsApp message and route to appropriate handler."""
    try:
        message_content = message.get("content", "")
        message_type = "image" if message.get("media_type") == "image" else "text"
        media_url = None
        
        # Download media if it's an image message
        if message.get("media_type") == "image":
            message_id = message.get("id")
            chat_jid = message.get("chat_jid")
            
            logger.info(f"📸 Image received from {phone_number}, message ID: {message_id}")
            
            async with whatsapp_mcp as mcp:
                media_url = await mcp.download_media(message_id, chat_jid)
                
                if media_url:
                    logger.info(f"✅ Media downloaded to: {media_url}")
                    
                    # Check if this is a payment screenshot - only handle payments via WhatsApp
                    is_payment_image = False
                    
                    try:
                        fund_handler = FundHandler(supabase_client)
                        
                        # First priority: Check if user is explicitly waiting for payment screenshot
                        if fund_handler.is_waiting_for_payment_screenshot(phone_number):
                            is_payment_image = True
                            logger.info(f"💳 User is waiting for payment screenshot - processing payment")
                        else:
                            # Second priority: Check for pending payments for this user
                            pending_payments = await fund_handler._get_pending_payments(user_id)
                            if pending_payments:
                                is_payment_image = True
                                logger.info(f"💳 User has {len(pending_payments)} pending payments - processing payment")
                            else:
                                # Third priority: Check message content for strong payment indicators
                                strong_payment_keywords = [
                                    "payment", "paid", "upi", "transaction", "screenshot", 
                                    "fund", "money", "sent", "done", "complete", "verify payment",
                                    "₹", "rupees", "rs", "deposit", "added money", "payment done"
                                ]
                                
                                if (message_content and 
                                    any(keyword in message_content.lower() for keyword in strong_payment_keywords)):
                                    is_payment_image = True
                                    logger.info(f"💳 Strong payment keywords found - processing payment: '{message_content}'")
                                
                                # Fourth priority: Check if no message content (just image) and user has recent fund request
                                elif not message_content.strip():
                                    # Check if user recently started add funds flow (last 10 minutes)
                                    if phone_number in fund_handler.fund_state:
                                        is_payment_image = True
                                        logger.info(f"💳 User in fund flow, blank image message - processing payment")
                                    
                    except Exception as e:
                        logger.error(f"Error checking payment status: {e}")
                    
                    if is_payment_image:
                        logger.info(f"💳 Processing as payment screenshot for user {user_id}")
                        try:
                            if os.path.exists(media_url):
                                with open(media_url, 'rb') as f:
                                    image_data = f.read()
                                
                                logger.info(f"📄 Read {len(image_data)} bytes of image data")
                                
                                fund_handler = FundHandler(supabase_client)
                                payment_response = await fund_handler.handle_payment_screenshot(
                                    user_id, phone_number, image_data
                                )
                                
                                logger.info(f"💬 Payment response: {payment_response[:100]}...")
                                
                                # Send payment processing response
                                async with whatsapp_mcp as mcp:
                                    await mcp.send_message(phone_number, payment_response)
                                return
                                
                            else:
                                logger.error(f"❌ Downloaded media file not found: {media_url}")
                                
                        except Exception as e:
                            logger.error(f"❌ Error processing payment screenshot: {e}")
                            async with whatsapp_mcp as mcp:
                                await mcp.send_message(phone_number, "❌ Error processing your payment screenshot. Please try again or contact support.")
                            return
                    else:
                        # Not a payment image - redirect to web app for challenge verification
                        logger.info(f"📷 Image not identified as payment, redirecting to web app")
                        redirect_message = (
                            "📸 **I received your photo!**\n\n"
                            "For challenge verification, please use our web app:\n\n"
                            "🌐 **https://dare-you-succeed.vercel.app/**\n\n"
                            "✨ **Why use the web app?**\n"
                            "• Better image upload experience\n"
                            "• Instant AI verification feedback\n"
                            "• Clear verification status\n"
                            "• Easy challenge management\n\n"
                            "💡 Your photo will be processed much faster there!"
                        )
                        
                        async with whatsapp_mcp as mcp:
                            await mcp.send_message(phone_number, redirect_message)
                        return
                else:
                    logger.error(f"❌ Failed to download media for message {message_id}")
        
        # Route message to appropriate intent handler (will no longer handle images)
        response = await intent_router.route_message(
            user_id=user_id,
            phone_number=phone_number,
            message_content=message_content,
            message_type=message_type,
            media_url=media_url
        )
        
        # Send response back via WhatsApp MCP
        if response:
            async with whatsapp_mcp as mcp:
                await mcp.send_message(phone_number, response)
                
                # Check if response indicates UPI payment needed
                if "Payment Required:" in response and "UPI QR code" in response:
                    # Send the UPI QR code image from your attachment
                    upi_qr_path = "/Users/dev16/Documents/Test project/dare-you-succeed 3/upi_qr_code.jpeg"
                    
                    try:
                        # Send the UPI QR code image
                        success = await mcp.send_message_with_media(phone_number, "📱 Scan this QR code to complete payment:", upi_qr_path)
                        if not success:
                            logger.warning("Failed to send UPI QR code image")
                    except Exception as e:
                        logger.error(f"Error sending UPI QR code: {e}")
                
        else:
            logger.warning("No response generated for message")
                
    except Exception as e:
        logger.error(f"Message processing error: {e}")
        # Send error message to user
        error_msg = "Sorry, I encountered an error processing your message. Please try again."
        async with whatsapp_mcp as mcp:
            await mcp.send_message(phone_number, error_msg)

@app.post("/api/send-message")
async def send_message_endpoint(request: Request):
    """
    Manual endpoint to send WhatsApp messages (for testing).
    """
    try:
        payload = await request.json()
        phone_number = payload.get("phone_number")
        message = payload.get("message")
        
        if not phone_number or not message:
            raise HTTPException(status_code=400, detail="phone_number and message are required")
        
        async with whatsapp_mcp as mcp:
            success = await mcp.send_message(phone_number, message)
        
        return {
            "status": "success" if success else "failed",
            "phone_number": phone_number,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Manual message sending error: {e}")
        return handle_error(e)

@app.post("/api/send-reminder")
async def send_reminder_endpoint(request: Request):
    """
    Manual endpoint to trigger reminder sending (for testing).
    In production, this is handled by cron jobs.
    """
    try:
        from cron.reminder_job import ReminderJob
        
        reminder_job = ReminderJob(supabase_client, whatsapp_mcp)
        sent_count = await reminder_job.send_due_reminders()
        
        return {
            "status": "success",
            "reminders_sent": sent_count,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Reminder sending error: {e}")
        return handle_error(e)

@app.get("/api/recent-messages")
async def get_recent_messages(phone_number: str = None, hours: int = 24):
    """
    Get recent messages from WhatsApp MCP database.
    """
    try:
        messages = whatsapp_mcp.get_recent_messages(
            phone_number=phone_number,
            hours=hours,
            limit=50
        )
        
        return {
            "status": "success",
            "messages": messages,
            "count": len(messages),
            "phone_number": phone_number,
            "hours": hours
        }
    except Exception as e:
        logger.error(f"Error fetching recent messages: {e}")
        return handle_error(e)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return handle_error(exc)

if __name__ == "__main__":
    # Run with uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8001)),
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )