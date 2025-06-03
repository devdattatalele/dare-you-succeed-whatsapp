"""
Reminder Job - Send challenge reminders via WhatsApp MCP

This module handles sending automatic reminders to users about
their upcoming challenge deadlines.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from api.whatsapp_mcp import WhatsAppMCPClient
from services.supabase_client import SupabaseClient
from utils.logger import setup_logger
from utils.retry import with_retry

logger = setup_logger(__name__)

class ReminderJob:
    """Job for sending challenge deadline reminders."""
    
    def __init__(self, supabase_client: SupabaseClient, whatsapp_mcp: WhatsAppMCPClient):
        self.supabase = supabase_client
        self.whatsapp = whatsapp_mcp
    
    @with_retry(max_retries=3, delay=2.0)
    async def send_due_reminders(self) -> int:
        """
        Send all due reminders and return count sent.
        
        Returns:
            int: Number of reminders sent
        """
        try:
            # Get all due reminders
            due_reminders = await self.supabase.get_due_reminders()
            
            if not due_reminders:
                logger.info("No due reminders found")
                return 0
            
            sent_count = 0
            
            for reminder in due_reminders:
                try:
                    success = await self._send_reminder(reminder)
                    if success:
                        sent_count += 1
                        # Mark as sent
                        await self.supabase.mark_reminder_sent(reminder["id"])
                    else:
                        logger.error(f"Failed to send reminder {reminder['id']}")
                        
                except Exception as e:
                    logger.error(f"Error processing reminder {reminder['id']}: {e}")
            
            logger.info(f"Sent {sent_count}/{len(due_reminders)} reminders")
            return sent_count
            
        except Exception as e:
            logger.error(f"Error in send_due_reminders: {e}")
            raise
    
    async def _send_reminder(self, reminder: Dict[str, Any]) -> bool:
        """
        Send a single reminder message.
        
        Args:
            reminder: Reminder data from database
            
        Returns:
            bool: True if sent successfully
        """
        try:
            # Extract reminder details
            phone_number = reminder["profiles"]["phone"]
            challenge_title = reminder["challenges"]["title"]
            bet_amount = reminder["challenges"]["bet_amount"]
            challenge_id = reminder["challenge_id"]
            
            # Format reminder message
            message = self._format_reminder_message(
                challenge_title, 
                bet_amount,
                challenge_id
            )
            
            # Send via WhatsApp MCP
            async with self.whatsapp as mcp:
                success = await mcp.send_message(phone_number, message)
            
            if success:
                logger.info(f"Reminder sent to {phone_number} for challenge '{challenge_title}'")
                return True
            else:
                logger.error(f"Failed to send reminder to {phone_number}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending reminder: {e}")
            return False
    
    def _format_reminder_message(
        self, 
        challenge_title: str, 
        bet_amount: float,
        challenge_id: str
    ) -> str:
        """
        Format the reminder message.
        
        Args:
            challenge_title: Challenge title
            bet_amount: Bet amount
            challenge_id: Challenge ID
            
        Returns:
            str: Formatted reminder message
        """
        return f"""🚨 CHALLENGE REMINDER 🚨

⏰ Your challenge deadline is approaching!

📝 Challenge: {challenge_title}
💰 Stake: ₹{bet_amount}
🆔 ID: {challenge_id}

Don't forget to submit your proof before the deadline. Send a photo or update when you've completed the challenge!

You can also send "status" to check all your active challenges.

Good luck! 🎯"""

    async def send_challenge_completion_reminder(
        self, 
        phone_number: str, 
        challenge: Dict[str, Any]
    ) -> bool:
        """
        Send a specific reminder for challenge completion.
        
        Args:
            phone_number: User's phone number
            challenge: Challenge data
            
        Returns:
            bool: True if sent successfully
        """
        try:
            message = f"""⏳ Last chance reminder!

Your challenge "{challenge['title']}" is due soon!

💰 Stake: ₹{challenge['bet_amount']}
⏰ Deadline: {challenge['deadline']}

Send a photo or message to complete your challenge now, or you'll lose your stake!

Reply with your proof to complete the challenge. 📸"""

            async with self.whatsapp as mcp:
                success = await mcp.send_message(phone_number, message)
            
            if success:
                logger.info(f"Completion reminder sent to {phone_number}")
                return True
            else:
                logger.error(f"Failed to send completion reminder to {phone_number}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending completion reminder: {e}")
            return False
    
    async def send_challenge_success_notification(
        self, 
        phone_number: str, 
        challenge: Dict[str, Any],
        reward_amount: float
    ) -> bool:
        """
        Send notification for successful challenge completion.
        
        Args:
            phone_number: User's phone number
            challenge: Challenge data
            reward_amount: Amount credited back
            
        Returns:
            bool: True if sent successfully
        """
        try:
            message = f"""🎉 CHALLENGE COMPLETED! 🎉

Congratulations! You've successfully completed:

📝 "{challenge['title']}"
💰 Your ₹{challenge['bet_amount']} stake has been returned
🎁 Bonus: ₹{reward_amount - challenge['bet_amount']} reward

Your dedication paid off! 🌟

Send "balance" to check your current balance or "create challenge" to start a new one!"""

            async with self.whatsapp as mcp:
                success = await mcp.send_message(phone_number, message)
            
            if success:
                logger.info(f"Success notification sent to {phone_number}")
                return True
            else:
                logger.error(f"Failed to send success notification to {phone_number}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending success notification: {e}")
            return False
    
    async def send_challenge_failure_notification(
        self, 
        phone_number: str, 
        challenge: Dict[str, Any]
    ) -> bool:
        """
        Send notification for failed challenge.
        
        Args:
            phone_number: User's phone number
            challenge: Challenge data
            
        Returns:
            bool: True if sent successfully
        """
        try:
            message = f"""😞 Challenge Deadline Passed

Unfortunately, you didn't complete your challenge in time:

📝 "{challenge['title']}"
💸 ₹{challenge['bet_amount']} stake has been forfeited

Don't give up! Learn from this experience and create a new challenge.

Send "create challenge" to start fresh with better planning! 💪"""

            async with self.whatsapp as mcp:
                success = await mcp.send_message(phone_number, message)
            
            if success:
                logger.info(f"Failure notification sent to {phone_number}")
                return True
            else:
                logger.error(f"Failed to send failure notification to {phone_number}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending failure notification: {e}")
            return False

# Example usage for cron job
async def run_reminder_job():
    """Main function to run reminder job."""
    from services.supabase_client import SupabaseClient
    from api.whatsapp_mcp import whatsapp_mcp
    
    supabase = SupabaseClient()
    reminder_job = ReminderJob(supabase, whatsapp_mcp)
    
    try:
        sent_count = await reminder_job.send_due_reminders()
        logger.info(f"Reminder job completed - sent {sent_count} reminders")
    except Exception as e:
        logger.error(f"Reminder job failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_reminder_job()) 