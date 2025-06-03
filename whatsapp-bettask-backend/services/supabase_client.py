"""
Supabase Client Service

Provides abstraction layer for Supabase interactions including:
- Database operations (Postgres)
- File storage operations
- Authentication (Compatible with webapp)
- Real-time subscriptions
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import asyncio
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
from gotrue import UserAttributes
import os

from config.settings import settings
from utils.logger import setup_logger
from utils.retry import with_retry

logger = setup_logger(__name__)

class SupabaseClient:
    """Supabase client wrapper with enhanced functionality and webapp compatibility."""
    
    def __init__(self):
        """Initialize Supabase client."""
        self.url = settings.SUPABASE_URL
        self.service_key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.anon_key = settings.SUPABASE_ANON_KEY
        
        if not all([self.url, self.service_key, self.anon_key]):
            raise ValueError("Missing required Supabase environment variables")
        
        # Use service role key for admin operations (user creation, etc.)
        self.client = create_client(self.url, self.service_key)
        
        # Also create an anon client for regular operations
        self.anon_client = create_client(self.url, self.anon_key)
        
        logger.info("Supabase client initialized with auth support")
    
    async def health_check(self) -> bool:
        """
        Check if Supabase connection is healthy.
        
        Returns:
            bool: True if healthy
        """
        try:
            # Test with a simple query
            result = self.client.table("profiles").select("id").limit(1).execute()
            return True
        except Exception as e:
            logger.error(f"Supabase health check failed: {e}")
            return False
    
    # Auth User Management (Compatible with webapp)
    async def create_auth_user(self, email: str, password: str, full_name: str, phone: str) -> dict:
        """
        Create a new user using Supabase Auth with enhanced error handling.
        
        Args:
            email: User's email address
            password: User's password  
            full_name: User's full name
            phone: User's phone number
            
        Returns:
            dict: User data from Supabase Auth
            
        Raises:
            Exception: With specific error message based on the failure type
        """
        logger.info(f"Creating auth user for email: {email}, phone: {phone}")
        
        try:
            # Step 1: Check for conflicts
            existing_email = await self.get_user_by_email(email)
            if existing_email:
                logger.error(f"User with email {email} already exists")
                raise Exception("Email already registered")
                
            existing_phone = await self.get_user_by_phone(phone)
            if existing_phone:
                logger.error(f"User with phone {phone} already exists")
                raise Exception("Phone number already registered")

            # Step 2: Create auth user first (this will fail if trigger is broken)
            try:
                auth_response = self.client.auth.admin.create_user({
                    "email": email,
                    "password": password,
                    "email_confirm": True,  # Auto-confirm email
                    "user_metadata": {
                        "full_name": full_name,
                        "phone": phone
                    }
                })
                
                if not auth_response.user:
                    raise Exception("Failed to create auth user")
                    
                user_id = auth_response.user.id
                logger.info(f"✅ Auth user created with ID: {user_id}")
                
            except Exception as auth_error:
                logger.error(f"Auth user creation failed: {auth_error}")
                # Try to parse the specific error
                if "Database error saving new user" in str(auth_error):
                    logger.error("🔥 TRIGGER IS BROKEN - Falling back to manual creation")
                    # We'll create the auth user differently
                    raise Exception("Database trigger error - using manual approach")
                else:
                    raise Exception(f"Auth creation failed: {auth_error}")

            # Step 3: If we get here, auth user was created successfully
            # Now manually create profile and wallet (in case trigger didn't work)
            try:
                # Create profile
                profile_data = {
                    "id": user_id,
                    "email": email,
                    "full_name": full_name,
                    "phone": phone
                }
                
                profile_result = self.client.table("profiles").insert(profile_data).execute()
                if profile_result.data:
                    logger.info(f"✅ Profile created manually for user {user_id}")
                else:
                    logger.warning(f"Profile creation returned no data for user {user_id}")
                
            except Exception as profile_error:
                logger.warning(f"Manual profile creation failed (trigger might have worked): {profile_error}")
                # This is OK if trigger already created it
            
            try:
                # Create wallet
                wallet_data = {
                    "user_id": user_id,
                    "balance": 0.00
                }
                
                wallet_result = self.client.table("wallets").insert(wallet_data).execute()
                if wallet_result.data:
                    logger.info(f"✅ Wallet created manually for user {user_id}")
                else:
                    logger.warning(f"Wallet creation returned no data for user {user_id}")
                    
            except Exception as wallet_error:
                logger.warning(f"Manual wallet creation failed (trigger might have worked): {wallet_error}")
                # This is OK if trigger already created it
            
            # Step 4: Return user data
            return {
                "id": user_id,
                "email": email,
                "full_name": full_name,
                "phone": phone
            }
            
        except Exception as e:
            error_message = str(e).lower()
            logger.error(f"Error creating auth user: {e}")
            
            # Provide user-friendly error messages
            if "email already" in error_message or "duplicate" in error_message:
                raise Exception("Email address is already registered")
            elif "phone already" in error_message:
                raise Exception("Phone number is already registered")
            elif "database error" in error_message or "trigger" in error_message:
                raise Exception("Database connection issue. Please try again in a moment.")
            elif "invalid email" in error_message:
                raise Exception("Please provide a valid email address")
            elif "weak password" in error_message:
                raise Exception("Password is too weak. Please use a stronger password.")
            else:
                raise Exception("Database connection issue. Please try again in a moment.")
    
    async def _ensure_profile_exists(self, user_id: str, email: str, full_name: str, phone: str) -> Dict[str, Any]:
        """Ensure profile exists for auth user (for database compatibility)."""
        try:
            # Check if profile already exists
            result = self.client.table("profiles").select("*").eq("id", user_id).execute()
            
            if result.data:
                # Update existing profile with phone
                profile_data = {
                    "phone": phone,
                    "email": email,
                    "full_name": full_name,
                    "updated_at": datetime.now().isoformat()
                }
                
                update_result = self.client.table("profiles").update(profile_data).eq("id", user_id).execute()
                logger.info(f"Updated existing profile for user {user_id}")
                return update_result.data[0] if update_result.data else result.data[0]
            else:
                # Create new profile
                profile_data = {
                    "id": user_id,  # Use auth user ID
                    "phone": phone,
                    "email": email,
                    "full_name": full_name,
                    "created_at": datetime.now().isoformat()
                }
                
                create_result = self.client.table("profiles").insert(profile_data).execute()
                logger.info(f"Created new profile for user {user_id}")
                return create_result.data[0] if create_result.data else {}
                
        except Exception as e:
            logger.error(f"Error ensuring profile exists: {e}")
            raise
    
    async def get_user_by_phone(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        Get user profile by phone number.
        
        Args:
            phone_number: User's phone number
            
        Returns:
            dict or None: User profile if found
        """
        try:
            clean_phone = phone_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            
            result = self.client.table("profiles").select("*").eq("phone", clean_phone).execute()
            
            if result.data:
                logger.info(f"Found existing user for phone {phone_number}")
                return result.data[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user by phone {phone_number}: {e}")
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get user profile by email address.
        
        Args:
            email: User's email address
            
        Returns:
            dict or None: User profile if found
        """
        try:
            result = self.client.table("profiles").select("*").eq("email", email).execute()
            
            if result.data:
                logger.info(f"Found existing user for email {email}")
                return result.data[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            return None

    # User Profile Management
    @with_retry(max_retries=3, delay=1.0)
    async def get_or_create_user_by_phone(self, phone_number: str) -> Dict[str, Any]:
        """
        Get user profile by phone number, create if doesn't exist.
        DEPRECATED: Use create_auth_user for new users to ensure webapp compatibility.
        
        Args:
            phone_number: User's phone number with country code
            
        Returns:
            dict: User profile data
        """
        try:
            # Clean phone number (remove spaces, dashes, etc.)
            clean_phone = phone_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            
            # Try to find existing user
            result = self.client.table("profiles").select("*").eq("phone", clean_phone).execute()
            
            if result.data:
                logger.info(f"Found existing user for phone {phone_number}")
                return result.data[0]
            
            # For temporary users (backward compatibility), return a temporary profile
            # New users should use create_auth_user instead
            logger.warning(f"Creating temporary user for phone {phone_number} - recommend using create_auth_user instead")
            
            # Create new user profile (temporary, not auth-based)
            import uuid
            temp_user_id = str(uuid.uuid4())
            new_profile = {
                "id": temp_user_id,
                "phone": clean_phone,
                "balance": 1000.0,  # Starting balance
                "created_at": datetime.now().isoformat(),
                "full_name": f"User {clean_phone[-4:]}"  # Temporary name
            }
            
            result = self.client.table("profiles").insert(new_profile).execute()
            
            if result.data:
                user_profile = result.data[0]
                logger.info(f"Created temporary user profile for phone {phone_number}")
                
                # Create initial wallet entry
                await self.create_wallet(user_profile["id"], 1000.0)
                
                return user_profile
            else:
                raise Exception("Failed to create user profile")
                
        except Exception as e:
            logger.error(f"Error getting/creating user by phone {phone_number}: {e}")
            raise

    async def update_user_balance(self, user_id: str, new_balance: float) -> bool:
        """
        Update user's balance in both profiles and wallets tables.
        
        Args:
            user_id: User ID
            new_balance: New balance amount
            
        Returns:
            bool: True if successful
        """
        try:
            # Update wallet table (primary source of truth)
            wallet_result = self.client.table("wallets").update({
                "balance": new_balance,
                "updated_at": datetime.now().isoformat()
            }).eq("user_id", user_id).execute()
            
            # Also update profiles table if balance column exists (for backward compatibility)
            try:
                profile_result = self.client.table("profiles").update({
                    "balance": new_balance
                }).eq("id", user_id).execute()
            except Exception as profile_error:
                logger.warning(f"Could not update profile balance (table may not have balance column): {profile_error}")
            
            return bool(wallet_result.data)
            
        except Exception as e:
            logger.error(f"Error updating user balance: {e}")
            return False
    
    # Wallet Management
    async def create_wallet(self, user_id: str, initial_balance: float = 1000.0) -> Dict[str, Any]:
        """Create wallet for user."""
        try:
            wallet_data = {
                "user_id": user_id,
                "balance": initial_balance,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            result = self.client.table("wallets").insert(wallet_data).execute()
            return result.data[0] if result.data else {}
            
        except Exception as e:
            logger.error(f"Error creating wallet: {e}")
            raise
    
    async def get_user_balance(self, user_id: str) -> float:
        """Get user's current balance."""
        try:
            result = self.client.table("wallets").select("balance").eq("user_id", user_id).execute()
            
            if result.data:
                return float(result.data[0]["balance"])
            else:
                # Create wallet if doesn't exist
                await self.create_wallet(user_id)
                return 1000.0
                
        except Exception as e:
            logger.error(f"Error getting user balance: {e}")
            return 0.0
    
    # Challenge Management
    async def create_challenge(
        self,
        user_id: str,
        title: str,
        bet_amount: float,
        deadline: datetime,
        task_type: str = "one-time",
        verification_method: str = "photo",
        verification_details: str = ""
    ) -> Dict[str, Any]:
        """
        Create a new challenge.
        
        Args:
            user_id: User creating the challenge
            title: Challenge title/description
            bet_amount: Amount to bet
            deadline: Challenge deadline
            task_type: Type of task (one-time, recurring)
            verification_method: How to verify completion
            verification_details: Additional verification details
            
        Returns:
            dict: Created challenge data
        """
        try:
            # Check if user has sufficient balance
            current_balance = await self.get_user_balance(user_id)
            if current_balance < bet_amount:
                raise ValueError(f"Insufficient balance. Current: ₹{current_balance}, Required: ₹{bet_amount}")
            
            # Create challenge
            challenge_data = {
                "user_id": user_id,
                "title": title,
                "amount": int(bet_amount),  # Convert to integer to match database schema
                "deadline": deadline.isoformat(),
                "status": "active",
                "task_type": task_type,
                "verification_method": verification_method,
                "verification_details": verification_details,
                "created_at": datetime.now().isoformat()
            }
            
            result = self.client.table("challenges").insert(challenge_data).execute()
            
            if result.data:
                challenge = result.data[0]
                
                # Deduct bet amount from balance
                new_balance = current_balance - bet_amount
                await self.update_user_balance(user_id, new_balance)
                
                # Record transaction
                await self.record_transaction(
                    user_id=user_id,
                    amount=-int(bet_amount),  # Convert to integer
                    transaction_type="deduction",
                    description=f"Bet placed for challenge: {title}",
                    challenge_id=challenge["id"]
                )
                
                logger.info(f"Created challenge '{title}' for user {user_id}")
                return challenge
            else:
                raise Exception("Failed to create challenge")
                
        except Exception as e:
            logger.error(f"Error creating challenge: {e}")
            raise
    
    async def get_user_challenges(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get user's challenges."""
        try:
            query = self.client.table("challenges").select("*").eq("user_id", user_id)
            
            if status:
                query = query.eq("status", status)
            
            result = query.order("created_at", desc=True).limit(limit).execute()
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error getting user challenges: {e}")
            return []
    
    async def update_challenge_status(self, challenge_id: str, status: str) -> bool:
        """Update challenge status."""
        try:
            result = self.client.table("challenges").update({
                "status": status
            }).eq("id", challenge_id).execute()
            
            if result.data:
                logger.info(f"Successfully updated challenge {challenge_id} status to {status}")
                return True
            else:
                logger.error(f"Failed to update challenge {challenge_id} status - no data returned")
                return False
            
        except Exception as e:
            logger.error(f"Error updating challenge status: {e}")
            return False
    
    async def get_active_challenges_near_deadline(self, hours_before: int = 2) -> List[Dict[str, Any]]:
        """Get active challenges approaching deadline."""
        try:
            cutoff_time = datetime.now() + timedelta(hours=hours_before)
            
            result = self.client.table("challenges").select(
                "*, profiles!inner(phone)"
            ).eq("status", "active").lt("deadline", cutoff_time.isoformat()).execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error getting challenges near deadline: {e}")
            return []
    
    # Task Submission Management
    async def create_task_submission(
        self,
        challenge_id: str,
        user_id: str,
        proof_url: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a task submission."""
        try:
            submission_data = {
                "challenge_id": challenge_id,
                "user_id": user_id,
                "proof_url": proof_url,
                "description": description,
                "verification_status": "pending",
                "created_at": datetime.now().isoformat()
            }
            
            result = self.client.table("task_submissions").insert(submission_data).execute()
            
            if result.data:
                # Update challenge status
                await self.update_challenge_status(challenge_id, "pending_verification")
                return result.data[0]
            else:
                raise Exception("Failed to create task submission")
                
        except Exception as e:
            logger.error(f"Error creating task submission: {e}")
            raise
    
    async def update_submission_verification(
        self,
        submission_id: str,
        verified: bool,
        ai_verdict: str,
        image_metadata: Optional[Dict] = None
    ) -> bool:
        """Update submission verification result."""
        try:
            update_data = {
                "verification_status": "approved" if verified else "failed",
                "ai_verdict": ai_verdict,
                "verified_at": datetime.now().isoformat()
            }
            
            if image_metadata:
                update_data["image_metadata"] = json.dumps(image_metadata)
            
            result = self.client.table("task_submissions").update(update_data).eq("id", submission_id).execute()
            
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"Error updating submission verification: {e}")
            return False
    
    # Transaction Management
    async def record_transaction(
        self,
        user_id: str,
        amount: float,
        transaction_type: str,
        description: str,
        challenge_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record a financial transaction."""
        try:
            transaction_data = {
                "user_id": user_id,
                "amount": amount,
                "transaction_type": transaction_type,
                "description": description,
                "challenge_id": challenge_id,
                "created_at": datetime.now().isoformat()
            }
            
            result = self.client.table("transactions").insert(transaction_data).execute()
            return result.data[0] if result.data else {}
            
        except Exception as e:
            logger.error(f"Error recording transaction: {e}")
            raise
    
    async def get_user_transactions(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get user's transaction history."""
        try:
            result = self.client.table("transactions").select("*").eq(
                "user_id", user_id
            ).order("created_at", desc=True).limit(limit).execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error getting user transactions: {e}")
            return []
    
    # Reminder Management
    async def create_reminder(
        self,
        user_id: str,
        challenge_id: str,
        remind_at: datetime
    ) -> Dict[str, Any]:
        """Create a reminder."""
        try:
            reminder_data = {
                "user_id": user_id,
                "challenge_id": challenge_id,
                "remind_at": remind_at.isoformat(),
                "sent": False,
                "created_at": datetime.now().isoformat()
            }
            
            result = self.client.table("reminders").insert(reminder_data).execute()
            return result.data[0] if result.data else {}
            
        except Exception as e:
            logger.error(f"Error creating reminder: {e}")
            raise
    
    async def get_due_reminders(self) -> List[Dict[str, Any]]:
        """Get reminders that are due to be sent."""
        try:
            result = self.client.table("reminders").select(
                "*, challenges!inner(title, amount), profiles!inner(phone)"
            ).eq("sent", False).lt("remind_at", datetime.now().isoformat()).execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error getting due reminders: {e}")
            return []
    
    async def mark_reminder_sent(self, reminder_id: str) -> bool:
        """Mark reminder as sent."""
        try:
            result = self.client.table("reminders").update({
                "sent": True,
                "sent_at": datetime.now().isoformat()
            }).eq("id", reminder_id).execute()
            
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"Error marking reminder as sent: {e}")
            return False
    
    # File Storage Operations
    async def upload_file(
        self,
        bucket: str,
        file_path: str,
        file_data: bytes,
        content_type: str = "image/jpeg"
    ) -> str:
        """
        Upload file to Supabase Storage.
        
        Args:
            bucket: Storage bucket name
            file_path: Path within bucket
            file_data: File content as bytes
            content_type: MIME type
            
        Returns:
            str: Public URL of uploaded file
        """
        try:
            # Upload file
            result = self.client.storage.from_(bucket).upload(
                file_path,
                file_data,
                file_options={
                    "content-type": content_type,
                    "cache-control": "3600"
                }
            )
            
            if result:
                # Get public URL
                public_url = self.client.storage.from_(bucket).get_public_url(file_path)
                logger.info(f"File uploaded successfully: {public_url}")
                return public_url
            else:
                raise Exception("File upload failed")
                
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            raise
    
    async def delete_file(self, bucket: str, file_path: str) -> bool:
        """Delete file from storage."""
        try:
            result = self.client.storage.from_(bucket).remove([file_path])
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False

    async def update_user_last_activity(self, user_id: str) -> bool:
        """Update user's last activity timestamp."""
        try:
            result = await self.client.table("profiles").update({
                "last_activity": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }).eq("id", user_id).execute()
            
            return len(result.data) > 0
            
        except Exception as e:
            logger.error(f"Failed to update user last activity: {e}")
            return False

    async def get_active_users(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get all users who have been active within the specified hours.
        Used for message polling to know which users to check for new messages.
        
        Args:
            hours: Number of hours to look back for activity
            
        Returns:
            List[Dict]: List of active user profiles
        """
        try:
            # Calculate cutoff time
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            result = await self.client.table("profiles").select(
                "id, phone, full_name, created_at, last_activity"
            ).gte(
                "last_activity", cutoff_time.isoformat()
            ).execute()
            
            logger.info(f"Found {len(result.data)} active users in last {hours} hours")
            return result.data
            
        except Exception as e:
            logger.error(f"Failed to get active users: {e}")
            # Fallback: get all users with phone numbers
            try:
                result = await self.client.table("profiles").select(
                    "id, phone, full_name, created_at, last_activity"
                ).not_.is_(
                    "phone", "null"
                ).execute()
                
                logger.info(f"Fallback: Found {len(result.data)} users with phone numbers")
                return result.data
                
            except Exception as fallback_error:
                logger.error(f"Fallback query also failed: {fallback_error}")
                return []

    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile data by user ID."""
        try:
            result = self.client.table("profiles").select("*").eq("id", user_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting user profile for {user_id}: {e}")
            return None
            
    async def get_active_challenges(self, user_id: str) -> List[Dict[str, Any]]:
        """Get active challenges for a user."""
        try:
            result = self.client.table("challenges").select("*").eq(
                "user_id", user_id).eq("status", "active").execute()
            
            if result.data:
                return result.data
            return []
        except Exception as e:
            logger.error(f"Error getting active challenges for {user_id}: {e}")
            return []

    async def authenticate_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user and return user data"""
        try:
            # Use anon client for auth
            auth_response = self.anon_client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if auth_response.user:
                # Get full profile data
                profile = await self.get_user_by_email(email)
                return profile
            else:
                return None
                
        except Exception as e:
            logger.error(f"Authentication error for {email}: {e}")
            return None

    async def get_user_wallet(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user wallet"""
        try:
            result = self.client.table("wallets").select("*").eq("user_id", user_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting wallet for user {user_id}: {e}")
            return None

    async def update_wallet_balance(self, user_id: str, new_balance: float) -> bool:
        """Update user wallet balance"""
        try:
            result = self.client.table("wallets").update({"balance": new_balance}).eq("user_id", user_id).execute()
            return bool(result.data)
        except Exception as e:
            logger.error(f"Error updating wallet balance for user {user_id}: {e}")
            return False

    async def add_transaction(self, user_id: str, amount: float, transaction_type: str, description: str, challenge_id: str = None) -> bool:
        """Add a transaction record"""
        try:
            transaction_data = {
                "user_id": user_id,
                "amount": amount,
                "transaction_type": transaction_type,
                "description": description
            }
            if challenge_id:
                transaction_data["challenge_id"] = challenge_id
                
            result = self.client.table("transactions").insert(transaction_data).execute()
            return bool(result.data)
        except Exception as e:
            logger.error(f"Error adding transaction: {e}")
            return False

    async def create_whatsapp_user(self, email: str, full_name: str, phone: str) -> Dict[str, Any]:
        """
        Create a WhatsApp-only user bypassing broken auth triggers.
        This creates profile and wallet directly without relying on Supabase Auth.
        
        Args:
            email: User's email address
            full_name: User's full name
            phone: User's phone number
            
        Returns:
            dict: User data with profile and wallet info
            
        Raises:
            Exception: With specific error message based on the failure type
        """
        logger.info(f"Creating WhatsApp user for email: {email}, phone: {phone}")
        
        try:
            # Step 1: Check for conflicts
            existing_email = await self.get_user_by_email(email)
            if existing_email:
                logger.error(f"User with email {email} already exists")
                raise Exception("Email already registered")
                
            existing_phone = await self.get_user_by_phone(phone)
            if existing_phone:
                logger.error(f"User with phone {phone} already exists")
                raise Exception("Phone number already registered")

            # Step 2: Generate unique user ID
            import uuid
            user_id = str(uuid.uuid4())
            
            # Step 3: Create profile directly
            profile_data = {
                "id": user_id,
                "email": email,
                "full_name": full_name,
                "phone": phone
            }
            
            profile_result = self.client.table("profiles").insert(profile_data).execute()
            
            if not profile_result.data:
                raise Exception("Failed to create user profile")
                
            logger.info(f"✅ Profile created for WhatsApp user {user_id}")
            
            # Step 4: Create wallet
            wallet_data = {
                "user_id": user_id,
                "balance": 0.00
            }
            
            wallet_result = self.client.table("wallets").insert(wallet_data).execute()
            
            if not wallet_result.data:
                # Rollback profile creation
                self.client.table("profiles").delete().eq("id", user_id).execute()
                raise Exception("Failed to create user wallet")
                
            logger.info(f"✅ Wallet created for WhatsApp user {user_id}")
            
            # Step 5: Return user data
            return {
                "id": user_id,
                "email": email,
                "full_name": full_name,
                "phone": phone,
                "wallet_id": wallet_result.data[0]["id"],
                "balance": wallet_result.data[0]["balance"],
                "user_type": "whatsapp_only"
            }
            
        except Exception as e:
            error_message = str(e).lower()
            logger.error(f"Error creating WhatsApp user: {e}")
            
            # Provide user-friendly error messages
            if "email already" in error_message or "duplicate" in error_message:
                raise Exception("Email address is already registered")
            elif "phone already" in error_message:
                raise Exception("Phone number is already registered")
            elif "invalid email" in error_message:
                raise Exception("Please provide a valid email address")
            else:
                raise Exception("Registration failed. Please try again.")

    async def create_user_with_password(self, email: str, password: str, full_name: str, phone: str) -> Dict[str, Any]:
        """
        Create a new user with password using custom authentication.
        This replaces Supabase Auth with our own password-based system.
        
        Args:
            email: User's email address
            password: User's password
            full_name: User's full name
            phone: User's phone number
            
        Returns:
            dict: User data
            
        Raises:
            Exception: With specific error message based on the failure type
        """
        logger.info(f"Creating user with password for email: {email}, phone: {phone}")
        
        try:
            # Step 1: Check for conflicts
            existing_email = await self.get_user_by_email(email)
            if existing_email:
                logger.error(f"User with email {email} already exists")
                raise Exception("Email already registered")
                
            existing_phone = await self.get_user_by_phone(phone)
            if existing_phone:
                logger.error(f"User with phone {phone} already exists")
                raise Exception("Phone number already registered")

            # Step 2: Use database function to create user with hashed password
            result = self.client.rpc('create_user_with_password', {
                'user_email': email,
                'user_password': password,
                'user_full_name': full_name,
                'user_phone': phone
            }).execute()
            
            if not result.data or len(result.data) == 0:
                raise Exception("Failed to create user account")
                
            user_data = result.data[0]
            logger.info(f"✅ User created with password: {user_data['user_id']}")
            
            return {
                "id": user_data["user_id"],
                "email": user_data["email"],
                "full_name": user_data["full_name"],
                "phone": user_data["phone"],
                "user_type": "password_auth"
            }
            
        except Exception as e:
            error_message = str(e).lower()
            logger.error(f"Error creating user with password: {e}")
            
            # Provide user-friendly error messages
            if "email already" in error_message or "duplicate" in error_message:
                raise Exception("Email address is already registered")
            elif "phone already" in error_message:
                raise Exception("Phone number is already registered")
            elif "invalid email" in error_message:
                raise Exception("Please provide a valid email address")
            elif "weak password" in error_message or "password" in error_message:
                raise Exception("Password is too weak. Please use a stronger password.")
            else:
                raise Exception("Registration failed. Please try again.")

    async def authenticate_user_with_password(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate user with email and password using custom authentication.
        
        Args:
            email: User's email address
            password: User's password
            
        Returns:
            dict or None: User profile if authenticated, None otherwise
        """
        try:
            # Use database function to authenticate
            result = self.client.rpc('authenticate_user', {
                'user_email': email,
                'user_password': password
            }).execute()
            
            if result.data and len(result.data) > 0:
                user_data = result.data[0]
                
                # Update last login
                self.client.table("profiles").update({
                    "last_login": datetime.now().isoformat()
                }).eq("id", user_data["user_id"]).execute()
                
                logger.info(f"✅ User authenticated: {email}")
                
                return {
                    "id": user_data["user_id"],
                    "email": user_data["email"],
                    "full_name": user_data["full_name"],
                    "phone": user_data["phone"],
                    "created_at": user_data["created_at"]
                }
            else:
                logger.warning(f"❌ Authentication failed for: {email}")
                return None
                
        except Exception as e:
            logger.error(f"Authentication error for {email}: {e}")
            return None 