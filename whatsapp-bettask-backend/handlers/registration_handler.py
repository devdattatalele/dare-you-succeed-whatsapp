"""
Registration Handler

Handles user registration flow for WhatsApp users.
Now uses Supabase Auth for webapp compatibility.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import re
import uuid

from services.supabase_client import SupabaseClient
from utils.logger import setup_logger

logger = setup_logger(__name__)

class RegistrationHandler:
    """Handler for user registration process via Supabase Auth."""
    
    def __init__(self, supabase_client: SupabaseClient):
        self.supabase_client = supabase_client
        
        # Track registration state for users going through the flow
        self.registration_state = {}
    
    async def handle_registration_flow(self, user_id: str, phone_number: str, message: str) -> str:
        """
        Handle the complete registration flow using Supabase Auth.
        Compatible with webapp authentication.
        """
        try:
            # Check if user already exists
            existing_user = await self.supabase_client.get_user_by_phone(phone_number)
            if existing_user:
                return (
                    f"👋 Welcome back! You're already registered.\n\n"
                    f"💰 Your balance: ₹{existing_user.get('balance', 0)}\n\n"
                    f"💡 What would you like to do?\n"
                    f"• Create a challenge: 'I will [goal], bet ₹[amount]'\n"
                    f"• Check balance: 'balance'\n"
                    f"• Add funds: 'add funds'\n"
                    f"• Help: 'help'"
                )
            
            # Get or initialize registration state
            if phone_number not in self.registration_state:
                self.registration_state[phone_number] = {
                    "stage": "email",
                    "phone": phone_number
                }
            
            state = self.registration_state[phone_number]
            
            # Handle different registration stages
            if state["stage"] == "email":
                return await self._handle_email_step(phone_number, message)
            elif state["stage"] == "password":
                return await self._handle_password_step(phone_number, message)
            elif state["stage"] == "name":
                return await self._handle_name_step(phone_number, message)
            elif state["stage"] == "confirmation":
                return await self._handle_confirmation_step(phone_number, message)
            else:
                # Reset state if confused
                self.registration_state[phone_number] = {
                    "stage": "email",
                    "phone": phone_number
                }
                return await self._handle_email_step(phone_number, message)
                
        except Exception as e:
            logger.error(f"Error in registration flow: {e}")
            # Clean up state on error
            if phone_number in self.registration_state:
                del self.registration_state[phone_number]
            return (
                "❌ Sorry, there was an error during registration. "
                "Please try again by typing 'register' or contact support."
            )
    
    async def _handle_email_step(self, phone_number: str, message: str) -> str:
        """Handle email collection step."""
        # If this is the first message, explain what we need
        if message.lower() in ["start", "register", "signup", "begin", "hello", "hi"]:
            self.registration_state[phone_number]["stage"] = "email"
            return (
                "👋 **Welcome to BetTask!**\n\n"
                "Let's create your account so you can access both WhatsApp and our web app.\n\n"
                "📧 **Please provide your email address:**\n"
                "This will be your login for the web app at:\n"
                "🌐 **dare-you-succeed.vercel.app**"
            )
        
        # Validate email
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, message.strip()):
            return (
                "❌ Please enter a valid email address.\n\n"
                "📧 **Example:** john@example.com\n\n"
                "This email will be used to log into our web app."
            )
        
        # Check if email already exists
        existing_user = await self.supabase_client.get_user_by_email(message.strip())
        if existing_user:
            return (
                "❌ This email is already registered.\n\n"
                "💡 **Options:**\n"
                "• Use a different email address\n"
                "• If this is your email, try logging in via the web app\n"
                "• Contact support if you need help\n\n"
                "📧 **Please provide a different email address:**"
            )
        
        # Save email and move to password step
        self.registration_state[phone_number]["email"] = message.strip()
        self.registration_state[phone_number]["stage"] = "password"
        
        return (
            "✅ Email saved!\n\n"
            "🔒 **Now create a password:**\n\n"
            "**Password requirements:**\n"
            "• At least 8 characters\n"
            "• Include numbers and letters\n"
            "• This will be used for web app login\n\n"
            "🔐 **Enter your password:**"
        )
    
    async def _handle_password_step(self, phone_number: str, message: str) -> str:
        """Handle password collection step."""
        password = message.strip()
        
        # Validate password
        if len(password) < 8:
            return (
                "❌ Password too short!\n\n"
                "🔒 **Password must be at least 8 characters.**\n\n"
                "Please enter a stronger password:"
            )
        
        if not re.search(r'[0-9]', password) or not re.search(r'[a-zA-Z]', password):
            return (
                "❌ Password too weak!\n\n"
                "🔒 **Password must include both letters and numbers.**\n\n"
                "Please enter a stronger password:"
            )
        
        # Save password and move to name step
        self.registration_state[phone_number]["password"] = password
        self.registration_state[phone_number]["stage"] = "name"
        
        return (
            "✅ Password saved!\n\n"
            "👤 **What's your full name?**\n\n"
            "This will be displayed in your profile.\n\n"
            "📝 **Enter your full name:**"
        )
    
    async def _handle_name_step(self, phone_number: str, message: str) -> str:
        """Handle name collection step."""
        full_name = message.strip()
        
        if len(full_name) < 2:
            return (
                "❌ Please enter your full name.\n\n"
                "👤 **Example:** John Doe\n\n"
                "📝 **Enter your full name:**"
            )
        
        # Save name and show confirmation
        self.registration_state[phone_number]["full_name"] = full_name
        self.registration_state[phone_number]["stage"] = "confirmation"
        
        state = self.registration_state[phone_number]
        
        return (
            f"📋 **Registration Summary:**\n\n"
            f"📧 **Email:** {state['email']}\n"
            f"📱 **Phone:** {state['phone']}\n"
            f"👤 **Name:** {state['full_name']}\n\n"
            f"🌐 **Web App Access:** dare-you-succeed.vercel.app\n"
            f"📱 **WhatsApp Access:** This chat\n\n"
            f"✅ **Type 'confirm' to create your account**\n"
            f"❌ **Type 'cancel' to start over**"
        )
    
    async def _handle_confirmation_step(self, phone_number: str, message: str) -> str:
        """Handle final confirmation and account creation."""
        message_lower = message.strip().lower()
        
        if message_lower in ["confirm", "yes", "y", "create", "ok", "okay"]:
            return await self._create_account(phone_number)
        elif message_lower in ["cancel", "no", "n", "restart", "start over"]:
            # Reset registration state
            del self.registration_state[phone_number]
            return (
                "❌ Registration cancelled.\n\n"
                "💡 Type 'register' to start over when you're ready."
            )
        else:
            return (
                "❓ Please confirm your choice:\n\n"
                "✅ Type 'confirm' to create your account\n"
                "❌ Type 'cancel' to start over"
            )
    
    async def _create_account(self, phone_number: str) -> str:
        """Create the user account using the new password-based authentication."""
        try:
            state = self.registration_state[phone_number]
            email = state["email"]
            password = state["password"]
            full_name = state["full_name"]
            phone = state["phone"]
            
            logger.info(f"Creating account with password for {email} with phone {phone}")
            
            # Use the new password-based authentication method
            user_data = await self.supabase_client.create_user_with_password(
                email=email,
                password=password,
                full_name=full_name,
                phone=phone
            )
            
            # Clean up registration state
            del self.registration_state[phone_number]
            
            logger.info(f"Successfully created password-based account for {email}")
            
            return (
                f"🎉 **Account Created Successfully!**\n\n"
                f"👤 **Welcome, {full_name}!**\n\n"
                f"📱 **WhatsApp Access:**\n"
                f"• Use this chat for challenges, balance, reminders\n"
                f"• Your account is ready to use!\n\n"
                f"🌐 **Web App Access:**\n"
                f"• Visit: dare-you-succeed.vercel.app\n"
                f"• Login with email: {email}\n"
                f"• Password: (the one you just created)\n"
                f"• Your data syncs automatically!\n\n"
                f"💰 **Starting Balance:** ₹0.00\n"
                f"💡 **Next Steps:**\n"
                f"• Add funds: 'add funds'\n"
                f"• Create challenge: 'I will [goal], bet ₹[amount]'\n"
                f"• Get help: 'help'\n\n"
                f"🚀 **Your accountability journey starts now!**\n\n"
                f"✨ **Both WhatsApp and web app use the same account now!**"
            )
            
        except Exception as e:
            logger.error(f"Error creating password-based account: {e}")
            
            # Don't delete state on error, let them try again
            return (
                "❌ **Account creation failed.**\n\n"
                "This might be due to:\n"
                "• Email already in use\n"
                "• Phone number already registered\n"
                "• Network connection issues\n\n"
                "💡 **Please try again:**\n"
                "• Type 'confirm' to retry\n"
                "• Type 'cancel' to start over\n"
                "• Contact support if problems persist"
            )
    
    async def is_user_registered(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        Check if user is registered via Supabase Auth.
        
        Args:
            phone_number: User's phone number
            
        Returns:
            dict or None: User profile if registered, None otherwise
        """
        try:
            user_profile = await self.supabase_client.get_user_by_phone(phone_number)
            return user_profile
            
        except Exception as e:
            logger.error(f"Error checking user registration: {e}")
            return None
    
    async def cleanup_expired_registrations(self):
        """Clean up registration states that have been inactive for too long."""
        try:
            # Remove states older than 1 hour
            current_time = datetime.now()
            expired_phones = []
            
            for phone, state in self.registration_state.items():
                # If no timestamp, add one
                if "started_at" not in state:
                    state["started_at"] = current_time
                else:
                    time_diff = current_time - state["started_at"]
                    if time_diff.total_seconds() > 3600:  # 1 hour
                        expired_phones.append(phone)
            
            for phone in expired_phones:
                del self.registration_state[phone]
                logger.info(f"Cleaned up expired registration state for {phone}")
                
        except Exception as e:
            logger.error(f"Error cleaning up registration states: {e}") 