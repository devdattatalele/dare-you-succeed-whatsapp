"""
Help Handler

Handles help and documentation operations:
- General help requests
- Feature explanations
- Usage examples
"""

import logging
from typing import Dict, Any

from ai.prompts import GeminiPrompts
from utils.logger import setup_logger

logger = setup_logger(__name__)

class HelpHandler:
    """Handles help and documentation requests."""
    
    def __init__(self):
        """Initialize help handler."""
        logger.info("Help handler initialized")
    
    async def handle_help(
        self,
        user_id: str,
        phone_number: str,
        message_content: str,
        extracted_data: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> str:
        """
        Handle help request.
        
        Args:
            user_id: User ID
            phone_number: User's phone number
            message_content: Original message content
            extracted_data: Data extracted by AI
            user_context: User context information
            
        Returns:
            str: Help response message
        """
        try:
            logger.info(f"Providing help for user {user_id}")
            
            # Check if user is asking about a specific topic
            message_lower = message_content.lower()
            
            if any(word in message_lower for word in ["timestamp", "camera", "photo", "watermark"]):
                return self._get_timestamp_help()
            elif any(word in message_lower for word in ["challenge", "bet", "create"]):
                return self._get_challenge_help()
            elif any(word in message_lower for word in ["proof", "photo", "submit"]):
                return self._get_proof_help()
            elif any(word in message_lower for word in ["balance", "money", "wallet"]):
                return self._get_balance_help()
            elif any(word in message_lower for word in ["reminder", "remind", "notification"]):
                return self._get_reminder_help()
            else:
                return self._get_general_help(user_context)
                
        except Exception as e:
            logger.error(f"Error providing help: {e}")
            return self._get_general_help(user_context)
    
    def _get_general_help(self, user_context: Dict[str, Any]) -> str:
        """Get general help content."""
        balance = user_context.get('balance', 0)
        active_challenges = user_context.get('active_challenges', 0)
        
        return f"""Hey! I'm here to help you achieve your goals through accountability betting 🎯

**How it works:**
Just tell me what you want to do - like "go to gym" or "study for 2 hours"
I'll help you set it up as a challenge with money on the line!

**Quick commands:**
💰 "balance" - check your wallet
📋 "my tasks" - see your challenges  
💵 "add money" - fund your wallet
📸 Send photos as proof when you complete tasks

**Examples:**
"I want to go gym tomorrow" 
"need to read for 1 hour"
"going to wake up at 6am"

The money makes it real - when you have skin in the game, you actually follow through! 💪

**Your current situation:**
💰 Balance: ₹{balance:.2f}
🎯 Active challenges: {active_challenges}
📈 Success rate: {user_context.get('success_rate', 0)}%

What goal do you want to work on? 🚀"""

    def _get_challenge_help(self) -> str:
        """Get challenge creation help."""
        return """🎯 **Creating Challenges - Super Easy!**

Just tell me what you want to do, like a friend would:
• "I want to go gym tomorrow"
• "Need to study for 2 hours today"
• "Going to wake up at 6am"

I'll ask how much you want to bet, and boom - challenge created! 💪

**Tips:**
✅ Be specific about your goal
✅ Start with smaller bets if you're new
✅ Pick realistic timeframes

What challenge do you want to create right now? 🚀"""

    def _get_proof_help(self) -> str:
        """Get proof submission help."""
        return """📸 **Submitting Proof - Easy Peasy!**

For the best experience, use our web app:
🌐 **https://dare-you-succeed.vercel.app/**

**Why the web app?**
• Select your specific challenge
• Upload high-quality photos  
• Get instant AI verification
• Much faster than WhatsApp!

**What makes good proof:**
✅ Clear, well-lit photos
✅ Shows you actually doing the thing
✅ Recent (not old photos!)

Ready to prove you crushed your goal? 💪"""

    def _get_balance_help(self) -> str:
        """Get balance and wallet help."""
        return """💰 **Your Wallet - Simple Stuff!**

**Check balance:** Just type "balance" 
**Add money:** Type "add funds" and I'll guide you
**Transaction history:** Type "history"

**How it works:**
• Add money to your wallet
• Bet on challenges 
• Win your money back when you complete them!
• Lose it if you don't (tough love! 😅)

Need to top up? Type "add funds" and let's do it! 💳"""

    def _get_reminder_help(self) -> str:
        """Get reminder help."""
        return """⏰ **Reminders - Coming Soon!**

I'm still learning how to remind you about stuff! 😅

For now, here's what you can do:
• Set phone alarms ⏰
• Use calendar notifications 📅
• Check "my challenges" regularly

The best reminder? Put money on the line - you won't forget! 💪

What challenge do you want to work on today? 🎯"""

    def _get_timestamp_help(self) -> str:
        """Get timestamp/camera help."""
        return """📸 **Photo Tips - Make It Count!**

**For best results:**
✅ Take photos in good lighting
✅ Show yourself actually doing the activity
✅ Don't use old photos (we can tell! 😉)
✅ Make it clear what you're doing

**Camera tips:**
• Use your phone's main camera
• Hold steady for sharp images
• Show the activity in progress

**Verification:**
Use our web app for best results: https://dare-you-succeed.vercel.app/

Ready to snap some proof? 📱💪"""

    def get_main_help(self) -> str:
        """Get main help message with all available commands."""
        return """Hey! I'm here to help you achieve your goals through accountability betting 🎯

**How it works:**
Just tell me what you want to do - like "go to gym" or "study for 2 hours"
I'll help you set it up as a challenge with money on the line!

**Quick commands:**
💰 "balance" - check your wallet
📋 "my tasks" - see your challenges  
💵 "add money" - fund your wallet
📸 Send photos as proof when you complete tasks

**Examples:**
"I want to go gym tomorrow" 
"need to read for 1 hour"
"going to wake up at 6am"

The money makes it real - when you have skin in the game, you actually follow through! 💪

What goal do you want to work on? 🚀""" 