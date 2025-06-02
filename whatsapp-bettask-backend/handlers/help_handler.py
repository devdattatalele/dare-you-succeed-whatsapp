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
        
        return f"""📚 **BetTask Help Guide**

Welcome to BetTask - Your WhatsApp Accountability Partner! 💪

🎯 **Create Challenge**: "I want to [goal], bet ₹[amount]"
📸 **Submit Proof**: Send photo/video of completion
📋 **My Challenges**: Type "my challenges" or "list"
💰 **Check Balance**: Type "balance" or "wallet"
⏰ **Set Reminder**: "Remind me [when]"
📊 **History**: Type "transactions" or "history"
❌ **Cancel**: Type "cancel challenge"

**💡 Examples:**
• "Go to gym tomorrow, bet ₹200"
• "Read 20 pages today, ₹150"
• "No social media for 6 hours, ₹100"
• "Wake up at 6am, ₹250"

**📈 Your Stats:**
Balance: ₹{balance:.2f}
Active: {active_challenges} challenges
Success: {user_context.get('success_rate', 0)}%

**🚀 Quick Tips:**
✅ Be specific with goals
✅ Set realistic deadlines  
✅ Take clear proof photos
✅ Start with smaller bets

Need specific help? Ask about:
• "help with challenges"
• "help with proof"
• "help with balance"
• "help with reminders"

Ready to transform your life? Start now! 🌟"""

    def _get_challenge_help(self) -> str:
        """Get challenge-specific help."""
        return """🎯 **Challenge Creation Help**

**How to create challenges:**
Just tell me what you want to do and how much you want to bet!

**Format:**
"I want to [goal], bet ₹[amount]"

**✅ Good Examples:**
• "Go to the gym tomorrow, bet ₹200"
• "Read 30 pages today, ₹150"
• "No social media for 8 hours, ₹100"
• "Wake up at 6am tomorrow, ₹250"
• "Complete homework by 8pm, ₹180"

**❌ Avoid vague goals:**
• "Exercise" → "Go to gym for 1 hour"
• "Study" → "Read 20 pages of math book"
• "Sleep early" → "Sleep by 10pm tonight"

**💰 Betting Guidelines:**
• Start small: ₹50-100 for new habits
• Medium challenges: ₹150-300
• Hard goals: ₹400-500
• Max bet: ₹2000

**⏰ Deadline Tips:**
• "tomorrow" = next day 9pm
• "today" = end of today
• "in 6 hours" = exactly 6 hours
• "Monday 3pm" = next Monday 3pm

**🔄 I'll automatically:**
• Set reminders 2 hours before deadline
• Enhance your challenge with AI suggestions
• Lock your bet money
• Guide you through verification

Ready to create your first challenge? 💪"""

    def _get_proof_help(self) -> str:
        """Get proof submission help."""
        return """📸 **Proof Submission Help**

**🌐 Use Our Web App for Best Experience:**
Visit: **https://dare-you-succeed.vercel.app/**

**✨ Why use the web app?**
• 📱 Better photo upload quality
• 🤖 Instant AI verification feedback  
• 📊 Clear verification status
• 🎯 Easy challenge management
• ⚡ Faster processing
• 📈 Better success rate

**🚀 How it works:**
1. Open the web app link above
2. Log in with your account
3. Select the challenge to verify
4. Upload your proof photo/video
5. Get instant AI verification results
6. Celebrate your success! 🎉

**📱 For WhatsApp completion:**
• Text: "completed [challenge name]"
• Then use web app for proof upload

**💡 Pro Tips:**
✅ Take clear, well-lit photos
✅ Show the activity in progress
✅ Include relevant context
✅ Upload immediately after completion

Ready to submit proof? Use our web app! 🌟
🌐 **https://dare-you-succeed.vercel.app/**"""

    def _get_balance_help(self) -> str:
        """Get balance and transaction help."""
        return """💰 **Balance & Wallet Help**

**Check Balance:**
• Type "balance" or "wallet"
• See available + locked money
• View recent transactions

**Transaction History:**
• Type "history" or "transactions"
• See all deposits, bets, wins/losses
• Track your progress over time

**💳 How Your Wallet Works:**

**Starting Balance:** ₹1000
When you join, you get ₹1000 to start betting!

**Available Balance:**
Money you can use for new challenges

**Locked Money:**
Money currently bet on active challenges

**Total Wallet:**
Available + Locked = Your total money

**📊 Transaction Types:**

**💸 Bet Placed (Deduction):**
Money locked when you create a challenge

**💚 Challenge Won (Refund):**
Money returned when you complete successfully

**💔 Challenge Lost:**
Money lost when you fail to complete

**📈 Example Flow:**
1. Start: ₹1000 available
2. Create ₹200 challenge: ₹800 available, ₹200 locked
3. Complete challenge: ₹1000 available, ₹0 locked
4. Fail challenge: ₹800 available, ₹0 locked

**💡 Pro Tips:**
• Start with smaller bets (₹50-100)
• Track your success rate
• Use locked money as motivation
• Celebrate when you win money back!

**🎯 Your Goal:**
Build consistency and win back your money by completing challenges!

Ready to check your balance? Type "balance"! 💪"""

    def _get_reminder_help(self) -> str:
        """Get reminder-specific help."""
        return """🔔 **Reminder System Help**

**Automatic Reminders:**
I automatically set reminders 2 hours before every challenge deadline!

**Custom Reminders:**
You can also set additional reminders anytime.

**How to Set Reminders:**
"Remind me [when]"

**⏰ Time Formats:**

**Relative Time:**
• "Remind me in 2 hours"
• "Remind me in 30 minutes"
• "Remind me in 1 day"

**Specific Time:**
• "Remind me at 3pm"
• "Remind me tomorrow at 9am"
• "Remind me Monday 6pm"

**Before Deadline:**
• "Remind me 1 hour before deadline"
• "Remind me 30 minutes before"

**📱 Reminder Content:**
Each reminder includes:
• Challenge name
• Time remaining
• Amount at stake
• Quick action buttons

**💡 Smart Features:**
• Won't send reminders for past times
• Multiple reminders per challenge
• Automatic deadline warnings
• Motivational messages

**🎯 Reminder Strategy:**
• Set early reminder to start preparing
• Set close reminder for final push
• Use deadline reminders to avoid losses

**Examples:**
• "Remind me at 7am" (for gym challenges)
• "Remind me in 3 hours" (study sessions)
• "Remind me 1 hour before deadline" (safety net)

Ready to set a reminder? Just tell me when! ⏰"""

    def _get_timestamp_help(self) -> str:
        """Get timestamp-specific help."""
        return """📱 **Camera Timestamp Help**

**Why do I need timestamps?**
WhatsApp removes photo data, so we need visible timestamps to verify your photo was taken today!

**📱 How to Enable Camera Timestamp:**

**For Android:**
1. Open Camera app
2. Tap Settings ⚙️ (gear icon)  
3. Find "Watermark" or "Timestamp" option
4. Enable "Date & Time" watermark
5. Take your proof photo

**For Samsung:**
- Camera → Settings → Useful features → Watermark

**For Xiaomi/MIUI:**
- Camera → Settings → Watermark → Device watermark

**For iPhone:**
1. Download "Timestamp Camera" app (free)
2. Or use "Camera Timestamp" app
3. Take photo with visible date/time

**📷 Alternative Methods:**
• Screenshot with time visible
• Photo including phone's clock/time
• Use timestamp camera apps
• Photo with newspaper/date visible

**✅ What we need to see:**
• Today's date clearly visible
• Any format: DD/MM/YYYY, MM/DD/YYYY, etc.
• Time is optional, date is required
• Can be in any corner of the image

**❌ Common issues:**
• Old photos without timestamps
• Blurry or unreadable timestamps
• Wrong date showing
• No timestamp visible

**💡 Pro tip:** Take a test photo first to make sure the timestamp is clearly visible!

Need more help? Send "help" for general assistance."""

    def get_main_help(self) -> str:
        """Get main help message with all available commands."""
        return (
            "🤖 **BetTask - Your Personal Accountability System**\n\n"
            
            "💰 **Wallet Management:**\n"
            "• 'balance' - Check your wallet balance\n"
            "• 'add funds' - Add money to your wallet\n"
            "• 'withdraw' - Withdraw money from wallet\n\n"
            
            "🎯 **Challenge Management:**\n"
            "• 'I will [goal] bet ₹[amount]' - Create new challenge\n"
            "• 'my challenges' - View all your challenges\n"
            "• 'completed' - Mark challenge as done\n\n"
            
            "📸 **Challenge Verification:**\n"
            "• Use our web app: https://dare-you-succeed.vercel.app/\n"
            "• Better photo upload experience\n"
            "• Instant AI verification feedback\n\n"
            
            "ℹ️ **Information:**\n"
            "• 'help' - Show this help message\n"
            "• 'contact' - Get support contact info\n\n"
            
            "💡 **Example:**\n"
            "\"I will go to gym today bet ₹100\"\n\n"
            
            "📱 For the best experience, visit:\n"
            "🌐 **https://dare-you-succeed.vercel.app/**"
        ) 