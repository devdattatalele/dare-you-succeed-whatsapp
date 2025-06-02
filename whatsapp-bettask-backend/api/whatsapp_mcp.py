"""
WhatsApp MCP Client - Direct integration with WhatsApp MCP Bridge

This module provides a client for communicating with the WhatsApp MCP bridge
instead of using webhooks. It directly calls the bridge's REST API and
can also read messages from the SQLite database.
"""

import os
import json
import sqlite3
import asyncio
import aiohttp
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging

from config.settings import settings
from utils.logger import setup_logger
from utils.retry import with_retry

logger = setup_logger(__name__)

class WhatsAppMCPClient:
    """
    Client for interacting with WhatsApp MCP Bridge.
    
    Provides methods to send messages, download media, and read message history
    directly from the bridge's SQLite database and REST API.
    """
    
    def __init__(self):
        self.bridge_url = settings.WHATSAPP_MCP_BRIDGE_URL
        self.db_path = settings.WHATSAPP_MCP_DATABASE_PATH
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self.session
    
    @with_retry(max_retries=3, delay=1.0, backoff_factor=2.0)
    async def send_message(
        self, 
        phone_number: str, 
        message: str, 
        media_path: Optional[str] = None
    ) -> bool:
        """
        Send a WhatsApp message via the MCP bridge.
        
        Args:
            phone_number: Recipient phone number (e.g., "+1234567890")
            message: Text message content
            media_path: Optional path to media file to send
            
        Returns:
            bool: True if message sent successfully
        """
        try:
            session = await self.get_session()
            
            # Format phone number for WhatsApp (remove + and ensure proper format)
            recipient = phone_number.lstrip('+')
            
            payload = {
                "recipient": recipient,
                "message": message
            }
            
            if media_path:
                payload["media_path"] = media_path
            
            logger.info(f"Sending message to {phone_number}: {message[:50]}...")
            
            async with session.post(
                f"{self.bridge_url}/api/send",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    if result.get("success"):
                        logger.info(f"✅ Message sent successfully to {phone_number}")
                        return True
                    else:
                        logger.error(f"❌ Bridge reported failure: {result.get('message')}")
                        return False
                else:
                    error_text = await response.text()
                    logger.error(f"❌ HTTP {response.status}: {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Failed to send message to {phone_number}: {e}")
            return False
    
    @with_retry(max_retries=3, delay=1.0, backoff_factor=2.0)
    async def download_media(self, message_id: str, chat_jid: str) -> Optional[str]:
        """
        Download media from a WhatsApp message.
        
        Args:
            message_id: ID of the message containing media
            chat_jid: JID of the chat containing the message
            
        Returns:
            Optional[str]: Local file path if download successful, None otherwise
        """
        try:
            session = await self.get_session()
            
            payload = {
                "message_id": message_id,
                "chat_jid": chat_jid
            }
            
            logger.info(f"Downloading media for message {message_id}")
            
            async with session.post(
                f"{self.bridge_url}/api/download",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    if result.get("success"):
                        file_path = result.get("path")
                        logger.info(f"✅ Media downloaded to: {file_path}")
                        return file_path
                    else:
                        logger.error(f"❌ Download failed: {result.get('message')}")
                        return None
                else:
                    error_text = await response.text()
                    logger.error(f"❌ HTTP {response.status}: {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Failed to download media: {e}")
            return None
    
    def get_recent_messages(
        self, 
        phone_number: Optional[str] = None, 
        hours: int = 24,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get recent messages from the MCP bridge database.
        
        Args:
            phone_number: Filter by specific phone number (optional)
            hours: Number of hours to look back
            limit: Maximum number of messages to return
            
        Returns:
            List[Dict]: List of message dictionaries
        """
        try:
            if not os.path.exists(self.db_path):
                logger.warning(f"MCP database not found at: {self.db_path}")
                return []
            
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Calculate time threshold
            since_time = datetime.now() - timedelta(hours=hours)
            
            # Build query
            if phone_number:
                # Convert phone number to JID format
                jid = f"{phone_number.lstrip('+')}@s.whatsapp.net"
                query = """
                    SELECT * FROM messages 
                    WHERE chat_jid = ? AND timestamp > ?
                    ORDER BY timestamp DESC LIMIT ?
                """
                cursor.execute(query, (jid, since_time, limit))
            else:
                query = """
                    SELECT * FROM messages 
                    WHERE timestamp > ?
                    ORDER BY timestamp DESC LIMIT ?
                """
                cursor.execute(query, (since_time, limit))
            
            messages = []
            for row in cursor.fetchall():
                messages.append({
                    "id": row["id"],
                    "chat_jid": row["chat_jid"],
                    "sender": row["sender"],
                    "content": row["content"],
                    "timestamp": row["timestamp"],
                    "is_from_me": bool(row["is_from_me"]),
                    "media_type": row["media_type"],
                    "filename": row["filename"]
                })
            
            conn.close()
            logger.info(f"Retrieved {len(messages)} recent messages")
            return messages
            
        except Exception as e:
            logger.error(f"Failed to get recent messages: {e}")
            return []
    
    def get_user_chat_jid(self, phone_number: str) -> str:
        """
        Convert phone number to WhatsApp JID format.
        
        Args:
            phone_number: Phone number (e.g., "+1234567890")
            
        Returns:
            str: WhatsApp JID (e.g., "1234567890@s.whatsapp.net")
        """
        return f"{phone_number.lstrip('+')}@s.whatsapp.net"
    
    async def check_bridge_health(self) -> bool:
        """
        Check if the WhatsApp MCP bridge is running and healthy.
        
        Returns:
            bool: True if bridge is healthy
        """
        try:
            session = await self.get_session()
            
            async with session.get(f"{self.bridge_url}/") as response:
                if response.status == 200:
                    logger.info("✅ WhatsApp MCP bridge is healthy")
                    return True
                else:
                    logger.warning(f"⚠️ Bridge responded with status {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Bridge health check failed: {e}")
            return False
    
    def get_unread_messages(self, phone_number: str, since_timestamp: datetime) -> List[Dict[str, Any]]:
        """
        Get unread messages from a specific user since a timestamp.
        
        Args:
            phone_number: User's phone number
            since_timestamp: Get messages after this timestamp
            
        Returns:
            List[Dict]: List of new message dictionaries
        """
        try:
            if not os.path.exists(self.db_path):
                return []
            
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            jid = self.get_user_chat_jid(phone_number)
            
            query = """
                SELECT * FROM messages 
                WHERE chat_jid = ? AND timestamp > ? AND is_from_me = 0
                ORDER BY timestamp ASC
            """
            cursor.execute(query, (jid, since_timestamp))
            
            messages = []
            for row in cursor.fetchall():
                messages.append({
                    "id": row["id"],
                    "chat_jid": row["chat_jid"],
                    "sender": row["sender"],
                    "content": row["content"],
                    "timestamp": row["timestamp"],
                    "is_from_me": bool(row["is_from_me"]),
                    "media_type": row["media_type"],
                    "filename": row["filename"]
                })
            
            conn.close()
            return messages
            
        except Exception as e:
            logger.error(f"Failed to get unread messages: {e}")
            return []
    
    async def send_message_with_media(self, phone_number: str, message: str, media_path: str) -> bool:
        """
        Convenience method to send a message with media file.
        
        Args:
            phone_number: Recipient phone number
            message: Text message to accompany media
            media_path: Path to media file to send
            
        Returns:
            bool: True if message sent successfully
        """
        return await self.send_message(phone_number, message, media_path)

# Global instance for easy access
whatsapp_mcp = WhatsAppMCPClient() 