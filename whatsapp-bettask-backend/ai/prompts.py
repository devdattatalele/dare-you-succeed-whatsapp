"""
AI Prompts for Gemini Integration

Contains all prompts for:
1. Intent classification from WhatsApp messages
2. Image/video proof verification 
3. Natural language processing for challenge creation
4. Reminder parsing and scheduling
"""

from typing import Dict, Any, List
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class IntentClassificationResult:
    """Result of intent classification."""
    intent: str
    confidence: float
    extracted_data: Dict[str, Any]
    requires_clarification: bool = False
    clarification_question: str = ""

class GeminiPrompts:
    """Collection of prompts for Gemini AI."""
    
    @staticmethod
    def get_intent_classification_prompt(message: str, user_context: Dict[str, Any] = None) -> str:
        """
        Prompt for classifying user intent from WhatsApp message.
        
        Args:
            message: User's WhatsApp message
            user_context: Optional context about user (balance, active challenges, etc.)
            
        Returns:
            str: Formatted prompt for Gemini
        """
        context_info = ""
        if user_context:
            context_info = f"""
User Context:
- Current Balance: ₹{user_context.get('balance', 0)}
- Active Challenges: {user_context.get('active_challenges', 0)}
- Recent Activity: {user_context.get('recent_activity', 'None')}
"""
        
        return f"""You are an AI assistant for a WhatsApp-based self-accountability betting system called "BetTask". 

Analyze this user message and classify the intent. Return a JSON response with the following structure:
{{
    "intent": "intent_name",
    "confidence": 0.95,
    "extracted_data": {{}},
    "requires_clarification": false,
    "clarification_question": ""
}}

Available Intents:
1. "create_challenge" - User wants to create a new challenge/bet
2. "submit_proof" - User is submitting proof for an existing challenge
3. "list_challenges" - User wants to see their active challenges
4. "get_balance" - User wants to check their balance
5. "set_reminder" - User wants to set a reminder for a challenge
6. "help" - User needs help or instructions
7. "cancel_challenge" - User wants to cancel a challenge
8. "transaction_history" - User wants to see transaction history
9. "general_chat" - General conversation not related to main features

{context_info}

User Message: "{message}"

For "create_challenge" intent, extract:
- "title": The challenge description
- "amount": Bet amount (if mentioned)
- "deadline": When it should be completed (parse natural language)
- "verification_method": How to verify (photo, description, etc.)

For "submit_proof" intent, extract:
- "challenge_description": Which challenge this relates to
- "proof_type": "photo", "video", or "text"

For "set_reminder" intent, extract:
- "reminder_time": When to remind (parse natural language)
- "challenge_reference": Which challenge to remind about

Example responses:

For "I want to go to the gym tomorrow, bet ₹200":
{{
    "intent": "create_challenge",
    "confidence": 0.92,
    "extracted_data": {{
        "title": "Go to the gym",
        "amount": 200,
        "deadline": "tomorrow",
        "verification_method": "photo"
    }}
}}

For "Here's my workout photo":
{{
    "intent": "submit_proof", 
    "confidence": 0.88,
    "extracted_data": {{
        "proof_type": "photo",
        "challenge_description": "workout"
    }}
}}

Analyze the message and respond with JSON only:"""

    @staticmethod
    def get_image_verification_prompt(
        challenge_title: str,
        verification_details: str,
        image_description: str = ""
    ) -> str:
        """
        Prompt for verifying image/video proof against challenge requirements.
        
        Args:
            challenge_title: The challenge being verified
            verification_details: Specific requirements for verification
            image_description: Optional description of the image content
            
        Returns:
            str: Formatted prompt for Gemini Vision
        """
        return f"""You are an AI verifier for a self-accountability betting system. Analyze this image/video proof and determine if it satisfies the challenge requirements.

Challenge: "{challenge_title}"
Verification Requirements: "{verification_details}"
{f"Image Description: {image_description}" if image_description else ""}

Respond with JSON in this exact format:
{{
    "verified": true/false,
    "confidence": 0.85,
    "verdict": "Detailed explanation of your decision",
    "concerns": ["List any concerns or red flags"],
    "suggestions": ["Suggestions for better proof if rejected"]
}}

Verification Guidelines:
1. Check if the image clearly shows evidence of completing the challenge
2. Look for signs of authenticity (not staged, recent timestamp if visible)
3. Ensure the proof matches the specific requirements
4. Be reasonably lenient but maintain standards
5. Consider context and effort demonstrated

Common Challenge Types & Verification:
- Gym/Workout: Look for gym equipment, exercise in progress, sweat, workout clothes
- Reading: Book pages, reading position, notes, highlighting
- Sleep/Wake: Alarm clocks, bed, timestamps, natural lighting for morning
- No Social Media: App usage screenshots, screen time reports
- Healthy Eating: Fresh meal preparation, healthy ingredients
- Study/Work: Books, notes, computer setup, focused environment

Be strict enough to prevent cheating but fair enough to recognize genuine effort.

Analyze the image and provide your verification decision:"""

    @staticmethod
    def get_challenge_suggestions_prompt(partial_description: str) -> str:
        """
        Prompt for suggesting challenge improvements and details.
        
        Args:
            partial_description: User's initial challenge description
            
        Returns:
            str: Formatted prompt for challenge enhancement
        """
        return f"""You are an AI coach for a self-accountability betting system. A user wants to create this challenge:

"{partial_description}"

Help improve their challenge by providing suggestions. Respond with JSON:
{{
    "improved_title": "Clear, specific challenge title",
    "suggested_amount": 200,
    "suggested_deadline": "24 hours",
    "verification_method": "photo",
    "verification_details": "Specific instructions for proof",
    "motivational_tip": "Encouraging message",
    "difficulty_level": "easy/medium/hard"
}}

Guidelines:
1. Make titles specific and measurable
2. Suggest realistic deadlines
3. Recommend appropriate bet amounts (₹50-500 based on difficulty)
4. Provide clear verification instructions
5. Add motivational encouragement

Common Challenge Categories:
- Fitness: Gym visits, workouts, runs, steps
- Learning: Reading, studying, courses, skills
- Productivity: Work tasks, organization, time management
- Health: Sleep, diet, meditation, habits
- Creative: Writing, art, music, projects

Enhance this challenge:"""

    @staticmethod
    def get_reminder_parsing_prompt(reminder_request: str) -> str:
        """
        Prompt for parsing natural language reminder requests.
        
        Args:
            reminder_request: User's reminder request in natural language
            
        Returns:
            str: Formatted prompt for reminder parsing
        """
        return f"""Parse this natural language reminder request into structured data.

User Request: "{reminder_request}"

Respond with JSON:
{{
    "reminder_time": "2024-01-15 14:30:00",
    "hours_before_deadline": 2,
    "reminder_type": "deadline/custom",
    "message": "Custom reminder message if specified",
    "valid": true,
    "error": ""
}}

Supported formats:
- "Remind me in 2 hours"
- "Set reminder for tomorrow at 3pm" 
- "Remind me 1 hour before deadline"
- "Wake me up at 6am"
- "Daily reminder at 9am"

Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Parse the request:"""

    @staticmethod
    def get_conversation_response_prompt(
        message: str,
        user_context: Dict[str, Any],
        conversation_history: List[str] = None
    ) -> str:
        """
        Prompt for generating conversational responses.
        
        Args:
            message: User's message
            user_context: User information and context
            conversation_history: Recent conversation history
            
        Returns:
            str: Formatted prompt for conversational response
        """
        history_text = ""
        if conversation_history:
            history_text = "\n".join(conversation_history[-5:])  # Last 5 messages
        
        return f"""You are a helpful, motivational AI assistant for BetTask, a WhatsApp-based self-accountability betting system.

User Context:
- Balance: ₹{user_context.get('balance', 0)}
- Active Challenges: {user_context.get('active_challenges', 0)}
- Success Rate: {user_context.get('success_rate', 0)}%
- Join Date: {user_context.get('join_date', 'Recently')}

{f"Recent Conversation:\n{history_text}\n" if history_text else ""}

User Message: "{message}"

Respond in a friendly, encouraging way. Keep responses concise (2-3 sentences max) and relevant to their self-improvement journey. 

Guidelines:
- Be supportive and motivational
- Provide actionable advice when appropriate
- Celebrate achievements
- Encourage when they're struggling
- Use emojis appropriately (but not excessively)
- Stay focused on accountability and self-improvement

Generate a helpful response:"""

    @staticmethod
    def get_help_content_prompt(specific_topic: str = None) -> str:
        """
        Generate help content for users.
        
        Args:
            specific_topic: Optional specific topic for help
            
        Returns:
            str: Help content
        """
        if specific_topic:
            return f"""Provide detailed help about: {specific_topic}

Format as a clear, step-by-step guide for WhatsApp users. Include:
1. What it is
2. How to use it  
3. Examples
4. Tips for success

Keep it concise but comprehensive."""
        
        return """📚 **BetTask Help Guide**

🎯 **Create Challenge**: "I want to [goal], bet ₹[amount]"
📸 **Submit Proof**: Send photo/video of completion
📋 **My Challenges**: Type "my challenges" or "list"
💰 **Check Balance**: Type "balance" or "wallet"
⏰ **Set Reminder**: "Remind me [when]"
📊 **History**: Type "transactions" or "history"

**Examples:**
- "Go to gym tomorrow, bet ₹200"
- "Read 20 pages today, ₹150"
- "No social media for 6 hours, ₹100"

**Tips:**
✅ Be specific with goals
✅ Set realistic deadlines  
✅ Take clear proof photos
✅ Start with smaller bets

Need specific help? Ask about any feature! 💪"""

    @staticmethod
    def get_payment_verification_prompt(
        expected_amount: float,
        expected_upi_id: str,
        payment_time_window_hours: int = 24
    ) -> str:
        """
        Prompt for verifying UPI payment screenshots.
        
        Args:
            expected_amount: The amount user said they would pay
            expected_upi_id: The UPI ID they should have paid to
            payment_time_window_hours: How recent the payment should be
            
        Returns:
            str: Formatted prompt for Gemini Vision
        """
        # Get current time for timestamp verification
        current_time = datetime.now()
        current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
        earliest_valid_time = (current_time - timedelta(hours=payment_time_window_hours)).strftime('%Y-%m-%d %H:%M:%S')
        
        return f"""You are an AI payment verifier for a financial system. Analyze this UPI payment screenshot and verify if it's a valid payment.

Expected Payment Details:
- Expected Amount: ₹{expected_amount}
- Expected Recipient UPI ID: {expected_upi_id}
- Payment Window: Last {payment_time_window_hours} hours

Current Time Information:
- Current Date/Time: {current_time_str}
- Earliest Valid Payment Time: {earliest_valid_time}
- Time Zone: IST (Indian Standard Time)

Respond with JSON in this exact format:
{{
    "verified": true/false,
    "confidence": 0.95,
    "amount_paid": 50.00,
    "recipient_upi": "devtalele0@okhdfcbank",
    "transaction_status": "SUCCESS/FAILED/PENDING",
    "timestamp_valid": true/false,
    "amount_matches": true/false,
    "upi_matches": true/false,
    "verdict": "Detailed explanation of verification result",
    "concerns": ["Any issues found"],
    "suggested_action": "credit_full/credit_partial/reject/manual_review"
}}

Verification Checklist:
1. **Amount Verification**: 
   - Extract the exact amount from the screenshot
   - Check if it matches expected amount (₹{expected_amount})
   - If different, note the actual amount

2. **UPI ID Verification**:
   - Look for recipient UPI ID: {expected_upi_id}
   - Check "To" or "Paid to" field
   - Verify it matches exactly

3. **Transaction Status**:
   - Look for "SUCCESS", "COMPLETED", "DONE" indicators
   - Check for any failure messages
   - Verify payment went through

4. **Timestamp Verification** (CRITICAL):
   - Look for transaction date/time in the screenshot
   - Current time is: {current_time_str}
   - Payment must be after: {earliest_valid_time}
   - Check for "Today", "Yesterday", or specific timestamps
   - Look for time in format like "15:30", "3:30 PM", etc.
   - If timestamp shows old date (before {earliest_valid_time}), mark timestamp_valid=false
   - Be strict about this - old screenshots should be rejected

5. **Authenticity Check**:
   - Look for UPI app interface (GPay, PhonePe, Paytm, etc.)
   - Check for transaction ID
   - Verify screenshot isn't edited/fake

6. **Screenshot Quality**:
   - Image should be clear and readable
   - All important details visible
   - Not cropped to hide information

Decision Logic:
- IF amount matches AND UPI matches AND status=SUCCESS AND timestamp valid → "credit_full"
- IF amount differs but payment valid AND timestamp valid → "credit_partial" (credit actual amount)
- IF amount too low (less than 50% expected) → "manual_review"
- IF UPI wrong or status failed → "reject"
- IF timestamp invalid (old payment) → "reject"
- IF screenshot unclear/suspicious → "manual_review"

Be thorough but fair. Users might pay slightly different amounts or use different UPI apps.
IMPORTANT: Reject old screenshots with invalid timestamps!

Analyze the payment screenshot now:""" 