"""
AI Handler for BetTask

Handles AI-powered operations like verification and natural language understanding.
Uses Gemini AI to understand user intents and context.
"""

import re
import json
import base64
import logging
from typing import Dict, Any, List, Optional

from utils.logger import setup_logger

logger = setup_logger(__name__)

class AIHandler:
    """
    Handles AI-powered operations like verification and natural language understanding.
    Uses Gemini AI to understand user intents and context.
    """
    
    def __init__(self, supabase_client):
        """Initialize with Supabase client for data retrieval."""
        self.supabase_client = supabase_client
        self.gemini_client = None
        
        try:
            # Lazily import to avoid errors if AI features are disabled
            from ai.gemini_client import GeminiClient
            self.gemini_client = GeminiClient()
        except Exception as e:
            logger.warning(f"AI Handler disabled: {e}")
            
    async def analyze_message_context(self, user_id: str, message: str):
        """
        Analyze a message to extract context and meaning beyond basic patterns.
        Returns contextual insights about user's intent.
        """
        if not self.gemini_client:
            return {"is_valid": False, "reason": "AI features disabled"}
            
        try:
            # Get user context
            user_profile = await self.supabase_client.get_user_profile(user_id)
            if not user_profile:
                return {"is_valid": False, "reason": "User not found"}
            
            # Get active challenges for this user
            active_challenges = await self.supabase_client.get_active_challenges(user_id)
            
            # Generate a context-aware prompt
            prompt = f"""
            User ID: {user_id}
            User Balance: ₹{user_profile.get('balance', 0)}
            Active Challenges: {len(active_challenges) if active_challenges else 0}
            
            Message: "{message}"
            
            Analyze this message and extract the following:
            1. Primary intent (create_challenge, check_balance, add_funds, etc.)
            2. If it's a challenge creation intent, extract:
               - Goal description
               - Amount to bet (if specified)
               - Timeframe (if specified)
               - Is it recurring? (daily/weekly)
            3. Is the user asking about past transactions or history?
            4. Is the user trying to escape a conversation flow?
            
            Return ONLY the JSON with this structure:
            {{
                "intent": "primary_intent_here",
                "confidence": 0.0-1.0,
                "is_challenge_creation": true/false,
                "challenge_details": {{
                    "goal": "extracted_goal",
                    "amount": number_or_null,
                    "timeframe": "extracted_timeframe_or_null",
                    "is_recurring": true/false,
                    "frequency": "daily/weekly/null"
                }},
                "is_transaction_history": true/false,
                "is_escape_attempt": true/false
            }}
            """
            
            # Get AI analysis
            analysis = await self.gemini_client.generate_response(prompt)
            
            # Parse the response
            try:
                # Extract JSON from response (handle potential text wrapper)
                json_str = re.search(r'({.*})', analysis, re.DOTALL)
                if json_str:
                    return json.loads(json_str.group(1))
                return {"is_valid": False, "reason": "Invalid AI response format"}
            except Exception as e:
                logger.error(f"Error parsing AI response: {e}")
                return {"is_valid": False, "reason": f"Error parsing AI response: {e}"}
                
        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            return {"is_valid": False, "reason": f"Error in AI analysis: {e}"}
            
    async def verify_payment_screenshot(self, image_data: bytes):
        """
        Verify if an image is a valid payment screenshot.
        Returns confidence score and analysis.
        """
        if not self.gemini_client:
            return {"is_payment": True, "confidence": 0.5, "reason": "AI verification disabled, accepting by default"}
            
        try:
            # Convert bytes to base64 for Gemini
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            prompt = """
            Analyze this image and determine if it's a payment screenshot.
            
            Look for these indicators of a payment screenshot:
            1. UPI transaction confirmation
            2. Payment app interface (Google Pay, PhonePe, Paytm, etc.)
            3. Transaction ID or reference number
            4. Amount transferred
            5. Date and timestamp of payment
            6. Success/failure status indicators
            7. Bank or payment gateway logos
            
            Return ONLY a JSON with this structure:
            {
                "is_payment": true/false,
                "confidence": 0.0-1.0,
                "amount_detected": number_or_null,
                "payment_app": "detected_app_or_null",
                "transaction_id": "detected_id_or_null",
                "reason": "brief explanation"
            }
            """
            
            # Call Gemini Vision
            analysis = await self.gemini_client.analyze_image(prompt, image_base64)
            
            # Parse the response
            try:
                # Extract JSON from response (handle potential text wrapper)
                json_str = re.search(r'({.*})', analysis, re.DOTALL)
                if json_str:
                    return json.loads(json_str.group(1))
                return {"is_payment": False, "confidence": 0, "reason": "Invalid AI response format"}
            except Exception as e:
                logger.error(f"Error parsing AI payment verification: {e}")
                return {"is_payment": False, "confidence": 0, "reason": f"Error parsing AI response: {e}"}
                
        except Exception as e:
            logger.error(f"Error in payment verification: {e}")
            return {"is_payment": False, "confidence": 0, "reason": f"Error in verification: {e}"}
            
    async def detect_conversation_derailment(self, conversation_history: List[str]):
        """
        Detect if a conversation is getting derailed or the user is frustrated.
        Returns analysis to help the bot get back on track.
        """
        if not self.gemini_client:
            return {"derailed": False, "reason": "AI features disabled"}
            
        try:
            # Format conversation history for AI
            history_text = "\n".join([f"Message {i+1}: {msg}" for i, msg in enumerate(conversation_history[-5:])])
            
            prompt = f"""
            Analyze this conversation history and determine if the conversation is getting derailed
            or if the user seems frustrated:
            
            {history_text}
            
            Look for these indicators:
            1. Multiple repeated attempts with the same message
            2. Short, frustrated responses (e.g., "no", "wrong", "stop", etc.)
            3. Increasing message length indicating user trying to explain more
            4. Use of punctuation like "!!" or "???"
            
            Return ONLY a JSON with this structure:
            {{
                "derailed": true/false,
                "confidence": 0.0-1.0,
                "frustration_level": "low/medium/high",
                "reason": "brief explanation",
                "suggested_action": "reset/clarify/apologize/continue"
            }}
            """
            
            # Get AI analysis
            analysis = await self.gemini_client.generate_response(prompt)
            
            # Parse the response
            try:
                # Extract JSON from response
                json_str = re.search(r'({.*})', analysis, re.DOTALL)
                if json_str:
                    return json.loads(json_str.group(1))
                return {"derailed": False, "reason": "Invalid AI response format"}
            except Exception as e:
                logger.error(f"Error parsing AI derailment detection: {e}")
                return {"derailed": False, "reason": f"Error parsing AI response: {e}"}
                
        except Exception as e:
            logger.error(f"Error in derailment detection: {e}")
            return {"derailed": False, "reason": f"Error in detection: {e}"} 