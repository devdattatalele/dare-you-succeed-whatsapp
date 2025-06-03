"""
Challenge Handler

Handles all challenge-related operations:
- Creating new challenges
- Listing user challenges  
- Canceling challenges
- Challenge status management
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
import re

from services.supabase_client import SupabaseClient
from ai.gemini_client import GeminiClient
from utils.logger import setup_logger
from utils.date_parser import parse_natural_date

logger = setup_logger(__name__)

class ChallengeHandler:
    """Handles challenge-related operations."""
    
    def __init__(self, supabase_client: SupabaseClient, gemini_client: GeminiClient):
        """
        Initialize challenge handler.
        
        Args:
            supabase_client: Supabase client instance
            gemini_client: Gemini AI client instance
        """
        self.supabase = supabase_client
        self.gemini = gemini_client
        logger.info("Challenge handler initialized")
    
    async def handle_create_challenge(
        self,
        user_id: str,
        phone_number: str,
        message_content: str,
        extracted_data: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> str:
        """
        Handle challenge creation request.
        
        Args:
            user_id: User ID
            phone_number: User's phone number
            message_content: Original message content
            extracted_data: Data extracted by AI
            user_context: User context information
            
        Returns:
            str: Response message
        """
        try:
            logger.info(f"Creating challenge for user {user_id}")
            
            # Check if user has sufficient data to create challenge
            title = extracted_data.get("title", message_content)
            amount = extracted_data.get("amount")
            deadline_str = extracted_data.get("deadline")
            verification_method = extracted_data.get("verification_method", "photo")
            
            # If missing critical info, use AI to enhance the challenge
            if not amount or not deadline_str:
                enhanced = await self.gemini.enhance_challenge(title)
                
                if not amount:
                    amount = enhanced.get("suggested_amount", 100)
                if not deadline_str:
                    deadline_str = enhanced.get("suggested_deadline", "24 hours")
                
                verification_details = enhanced.get("verification_details", "")
                motivational_tip = enhanced.get("motivational_tip", "")
            else:
                verification_details = f"Submit {verification_method} proof of completion"
                motivational_tip = ""
            
            # Parse deadline
            try:
                deadline = parse_natural_date(deadline_str)
                if deadline <= datetime.now():
                    deadline = datetime.now() + timedelta(hours=24)  # Default to 24 hours
            except Exception as e:
                logger.warning(f"Could not parse deadline '{deadline_str}': {e}")
                deadline = datetime.now() + timedelta(hours=24)
            
            # Validate amount
            if not isinstance(amount, (int, float)):
                try:
                    amount = float(re.findall(r'\d+', str(amount))[0])
                except (IndexError, ValueError):
                    amount = 100.0
            
            amount = max(10.0, min(float(amount), 2000.0))  # Between ₹10-2000
            
            # Check if user has sufficient balance
            current_balance = user_context.get("balance", 0)
            if current_balance < amount:
                return f"""❌ **Insufficient Balance**

You need ₹{amount:.2f} but only have ₹{current_balance:.2f}.

💡 **Options:**
- Reduce your bet amount to ₹{current_balance:.2f} or less
- Try: "{title}, bet ₹{min(current_balance, 50)}"

Your balance: ₹{current_balance:.2f}"""
            
            # Create the challenge
            challenge = await self.supabase.create_challenge(
                user_id=user_id,
                title=title,
                bet_amount=amount,
                deadline=deadline,
                verification_method=verification_method,
                verification_details=verification_details
            )
            
            # Create default reminder (2 hours before deadline)
            reminder_time = deadline - timedelta(hours=2)
            if reminder_time > datetime.now():
                await self.supabase.create_reminder(
                    user_id=user_id,
                    challenge_id=challenge["id"],
                    remind_at=reminder_time
                )
            
            # Format success response
            deadline_formatted = deadline.strftime("%B %d, %Y at %I:%M %p")
            
            response = f"""✅ **Challenge Created Successfully!**

🎯 **{title}**
💰 Bet Amount: ₹{amount:.2f}
⏰ Deadline: {deadline_formatted}
📋 Verification: {verification_method.title()} proof required

💡 {verification_details}

🔔 You'll get a reminder 2 hours before the deadline.

New balance: ₹{current_balance - amount:.2f}

{motivational_tip if motivational_tip else "Good luck! 💪"}"""
            
            return response
            
        except ValueError as e:
            logger.error(f"Validation error creating challenge: {e}")
            return f"❌ Error: {str(e)}"
        except Exception as e:
            logger.error(f"Error creating challenge: {e}")
            return "❌ Sorry, I couldn't create your challenge. Please try again or contact support."
    
    async def handle_list_challenges(
        self,
        user_id: str,
        phone_number: str,
        message_content: str,
        extracted_data: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> str:
        """
        Handle listing user's challenges.
        
        Args:
            user_id: User ID
            phone_number: User's phone number
            message_content: Original message content
            extracted_data: Data extracted by AI
            user_context: User context information
            
        Returns:
            str: Response message with challenge list
        """
        try:
            logger.info(f"Listing challenges for user {user_id}")
            
            # Get user's challenges
            challenges = await self.supabase.get_user_challenges(user_id, limit=20)
            
            if not challenges:
                return """📋 **Your Challenges**

You don't have any challenges yet!

🎯 **Create your first challenge:**
"I want to [goal], bet ₹[amount]"

**Examples:**
- "Go to gym tomorrow, bet ₹200"
- "Read 20 pages today, ₹150"
- "No social media for 6 hours, ₹100"

Ready to start? 💪"""
            
            # Group challenges by status
            active_challenges = [c for c in challenges if c["status"] == "active"]
            pending_challenges = [c for c in challenges if c["status"] == "pending_verification"]
            completed_challenges = [c for c in challenges if c["status"] == "completed"]
            failed_challenges = [c for c in challenges if c["status"] == "failed"]
            
            response = "📋 **Your Challenges**\n\n"
            
            # Active challenges
            if active_challenges:
                response += "🟢 **Active Challenges:**\n"
                for challenge in active_challenges[:5]:  # Show max 5
                    deadline = datetime.fromisoformat(challenge["deadline"].replace('Z', '+00:00'))
                    # Make current time timezone-aware to match deadline
                    now = datetime.now(deadline.tzinfo) if deadline.tzinfo else datetime.now()
                    time_left = deadline - now
                    
                    if time_left.total_seconds() > 0:
                        hours_left = int(time_left.total_seconds() / 3600)
                        if hours_left > 24:
                            time_text = f"{hours_left // 24} days"
                        else:
                            time_text = f"{hours_left} hours"
                    else:
                        time_text = "⚠️ OVERDUE"
                    
                    response += f"• {challenge['title']} - ₹{challenge['amount']:.0f} ({time_text})\n"
                response += "\n"
            
            # Pending verification
            if pending_challenges:
                response += "🟡 **Pending Verification:**\n"
                for challenge in pending_challenges[:3]:
                    response += f"• {challenge['title']} - ₹{challenge['amount']:.0f}\n"
                response += "\n"
            
            # Recent completed
            if completed_challenges:
                response += f"✅ **Completed:** {len(completed_challenges)} challenges\n"
                if completed_challenges:
                    latest = completed_challenges[0]
                    response += f"Latest: {latest['title']}\n\n"
            
            # Recent failed
            if failed_challenges:
                response += f"❌ **Failed:** {len(failed_challenges)} challenges\n\n"
            
            # Summary stats
            total_bet = sum(c["amount"] for c in challenges)
            won_amount = sum(c["amount"] for c in completed_challenges)
            lost_amount = sum(c["amount"] for c in failed_challenges)
            
            response += f"""📊 **Summary:**
Total challenges: {len(challenges)}
Total bet: ₹{total_bet:.2f}
Won: ₹{won_amount:.2f}
Lost: ₹{lost_amount:.2f}
Success rate: {user_context.get('success_rate', 0)}%

💡 Submit proof for active challenges to avoid losing your bet!"""
            
            return response
            
        except Exception as e:
            logger.error(f"Error listing challenges: {e}")
            return "❌ Sorry, I couldn't fetch your challenges. Please try again."
    
    async def handle_cancel_challenge(
        self,
        user_id: str,
        phone_number: str,
        message_content: str,
        extracted_data: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> str:
        """
        Handle challenge cancellation request.
        
        Args:
            user_id: User ID
            phone_number: User's phone number
            message_content: Original message content
            extracted_data: Data extracted by AI
            user_context: User context information
            
        Returns:
            str: Response message
        """
        try:
            logger.info(f"Handling cancel request for user {user_id}")
            
            # Get active challenges
            active_challenges = await self.supabase.get_user_challenges(
                user_id, status="active"
            )
            
            if not active_challenges:
                return """❌ **No Active Challenges**

You don't have any active challenges to cancel.

📋 Type "list" to see all your challenges
🎯 Type "create challenge" to start a new one"""
            
            if len(active_challenges) == 1:
                # Auto-cancel the only active challenge
                challenge = active_challenges[0]
                
                # Update challenge status to cancelled
                await self.supabase.update_challenge_status(challenge["id"], "cancelled")
                
                # Refund the bet amount
                current_balance = await self.supabase.get_user_balance(user_id)
                new_balance = current_balance + challenge["amount"]
                await self.supabase.update_user_balance(user_id, new_balance)
                
                # Record refund transaction
                await self.supabase.record_transaction(
                    user_id=user_id,
                    amount=challenge["amount"],
                    transaction_type="refund",
                    description=f"Refund for cancelled challenge: {challenge['title']}",
                    challenge_id=challenge["id"]
                )
                
                return f"""✅ **Challenge Cancelled**

🎯 Challenge: {challenge['title']}
💰 Refunded: ₹{challenge['amount']:.2f}
💳 New balance: ₹{new_balance:.2f}

The challenge has been cancelled and your bet has been refunded."""
            
            else:
                # Multiple challenges - ask user to specify
                response = "❓ **Which challenge would you like to cancel?**\n\n"
                for i, challenge in enumerate(active_challenges[:5], 1):
                    deadline = datetime.fromisoformat(challenge["deadline"].replace('Z', '+00:00'))
                    time_left = deadline - datetime.now()
                    hours_left = int(time_left.total_seconds() / 3600)
                    
                    response += f"{i}. {challenge['title']} - ₹{challenge['amount']:.0f} ({hours_left}h left)\n"
                
                response += "\n💡 Reply with the number of the challenge you want to cancel (e.g., '1')"
                return response
                
        except Exception as e:
            logger.error(f"Error cancelling challenge: {e}")
            return "❌ Sorry, I couldn't cancel your challenge. Please try again or contact support."
    
    def _format_challenge_deadline(self, deadline_str: str) -> str:
        """Format deadline string for display."""
        try:
            deadline = datetime.fromisoformat(deadline_str.replace('Z', '+00:00'))
            return deadline.strftime("%B %d at %I:%M %p")
        except Exception:
            return deadline_str
    
    def _calculate_time_remaining(self, deadline_str: str) -> str:
        """Calculate and format time remaining until deadline."""
        try:
            deadline = datetime.fromisoformat(deadline_str.replace('Z', '+00:00'))
            time_left = deadline - datetime.now()
            
            if time_left.total_seconds() <= 0:
                return "⚠️ OVERDUE"
            
            hours = int(time_left.total_seconds() / 3600)
            if hours > 24:
                days = hours // 24
                return f"{days} day{'s' if days != 1 else ''}"
            else:
                return f"{hours} hour{'s' if hours != 1 else ''}"
                
        except Exception:
            return "Unknown" 