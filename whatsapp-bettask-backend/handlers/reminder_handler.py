"""
Reminder Handler

Handles reminder and notification operations:
- Setting custom reminders
- Parsing reminder requests
- Reminder management
"""

import logging
from typing import Dict, Any
from datetime import datetime, timedelta

from services.supabase_client import SupabaseClient
from ai.gemini_client import GeminiClient
from utils.logger import setup_logger
from utils.date_parser import parse_natural_date

logger = setup_logger(__name__)

class ReminderHandler:
    """Handles reminder operations."""
    
    def __init__(self, supabase_client: SupabaseClient, gemini_client: GeminiClient):
        """
        Initialize reminder handler.
        
        Args:
            supabase_client: Supabase client instance
            gemini_client: Gemini AI client instance
        """
        self.supabase = supabase_client
        self.gemini = gemini_client
        logger.info("Reminder handler initialized")
    
    async def handle_set_reminder(
        self,
        user_id: str,
        phone_number: str,
        message_content: str,
        extracted_data: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> str:
        """
        Handle reminder setting request.
        
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
            logger.info(f"Setting reminder for user {user_id}")
            
            # Get user's active challenges
            active_challenges = await self.supabase.get_user_challenges(
                user_id, status="active"
            )
            
            if not active_challenges:
                return """❌ **No Active Challenges**

You don't have any active challenges to set reminders for.

🎯 Create a challenge first:
"I want to [goal], bet ₹[amount]"

Then I'll automatically set reminders for you!"""
            
            # Parse reminder request using AI
            reminder_data = await self.gemini.parse_reminder_request(message_content)
            
            if not reminder_data.get("valid", False):
                return f"""❓ **Couldn't understand your reminder request**

{reminder_data.get('error', 'Please try again with a clearer format')}

✅ **Examples:**
• "Remind me in 2 hours"
• "Set reminder for tomorrow 3pm"
• "Remind me 1 hour before deadline"

📋 Your active challenges:"""
            
            # If multiple challenges, let user choose
            if len(active_challenges) > 1:
                response = "❓ **Which challenge should I remind you about?**\n\n"
                for i, challenge in enumerate(active_challenges[:5], 1):
                    deadline = datetime.fromisoformat(challenge["deadline"].replace('Z', '+00:00'))
                    time_left = deadline - datetime.now()
                    hours_left = int(time_left.total_seconds() / 3600)
                    
                    response += f"{i}. {challenge['title']} - ₹{challenge['bet_amount']:.0f} ({hours_left}h left)\n"
                
                response += f"\n💡 Reply with the number and I'll set the reminder you requested"
                return response
            
            # Single challenge - set reminder
            challenge = active_challenges[0]
            
            # Calculate reminder time
            if reminder_data.get("reminder_type") == "deadline":
                # Reminder before deadline
                hours_before = reminder_data.get("hours_before_deadline", 2)
                deadline = datetime.fromisoformat(challenge["deadline"].replace('Z', '+00:00'))
                reminder_time = deadline - timedelta(hours=hours_before)
            else:
                # Custom time
                reminder_time_str = reminder_data.get("reminder_time")
                if reminder_time_str:
                    reminder_time = datetime.fromisoformat(reminder_time_str)
                else:
                    # Fallback to 2 hours before deadline
                    deadline = datetime.fromisoformat(challenge["deadline"].replace('Z', '+00:00'))
                    reminder_time = deadline - timedelta(hours=2)
            
            # Check if reminder time is in the future
            if reminder_time <= datetime.now():
                return """⚠️ **Invalid Reminder Time**

The reminder time you specified has already passed.

💡 **Try:**
• "Remind me in 1 hour"
• "Remind me tomorrow at 9am"
• "Remind me 2 hours before deadline"

Current time: """ + datetime.now().strftime("%I:%M %p")
            
            # Create reminder
            reminder = await self.supabase.create_reminder(
                user_id=user_id,
                challenge_id=challenge["id"],
                remind_at=reminder_time
            )
            
            # Format response
            reminder_formatted = reminder_time.strftime("%B %d at %I:%M %p")
            challenge_deadline = datetime.fromisoformat(challenge["deadline"].replace('Z', '+00:00'))
            deadline_formatted = challenge_deadline.strftime("%B %d at %I:%M %p")
            
            return f"""✅ **Reminder Set!**

🔔 Reminder: {reminder_formatted}
🎯 Challenge: {challenge['title']}
⏰ Deadline: {deadline_formatted}
💰 Amount: ₹{challenge['bet_amount']:.2f}

I'll send you a WhatsApp message at the reminder time!

💡 You can set multiple reminders by typing "remind me [when]" again."""
            
        except Exception as e:
            logger.error(f"Error setting reminder: {e}")
            return "❌ Sorry, I couldn't set your reminder. Please try again with a clearer format like 'remind me in 2 hours'." 