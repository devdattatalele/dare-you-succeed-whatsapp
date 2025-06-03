"""
Gemini AI Client

Handles integration with Google's Gemini API for:
1. Text-based intent classification
2. Image/video verification using Gemini Vision
3. Natural language processing for challenges and reminders
"""

import json
import base64
import logging
from typing import Dict, Any, Optional, List, Union
import aiohttp
from PIL import Image
import io
import os
import re

from config.settings import settings
from utils.logger import setup_logger
from utils.retry import with_retry
from ai.prompts import GeminiPrompts, IntentClassificationResult

logger = setup_logger(__name__)

class GeminiClient:
    """Client for Google Gemini AI API."""
    
    def __init__(self):
        """Initialize Gemini client."""
        # Use settings which properly loads from .env file
        self.api_key = settings.GEMINI_API_KEY
        
        if self.api_key == "disabled":
            self.api_key = None
            logger.info("🔒 Gemini AI disabled (API key set to 'disabled')")
        elif self.api_key:
            logger.info(f"✅ Gemini AI initialized with API key: {self.api_key[:20]}...")
        else:
            self.api_key = None
            logger.warning("⚠️ Gemini API key not found - AI features disabled")
        
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.model = settings.GEMINI_MODEL  # Use model from settings
        self.session = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=60)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close(self):
        """Close aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def _call_gemini_api(self, prompt: str, temperature: float = 0.1) -> Optional[str]:
        """
        Make a call to Gemini API with text prompt.
        
        Args:
            prompt: Text prompt to send
            temperature: Temperature for response generation (0.0-1.0)
            
        Returns:
            str: AI response or None if failed
        """
        if not self.api_key:
            return None
            
        try:
            session = await self._get_session()
            
            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": 1000,
                    "candidateCount": 1
                }
            }
            
            url = f"{self.base_url}/models/{self.model}:generateContent"
            
            async with session.post(
                url,
                json=payload,
                headers={"x-goog-api-key": self.api_key}
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    
                    if "candidates" in result and result["candidates"]:
                        return result["candidates"][0]["content"]["parts"][0]["text"]
                    else:
                        logger.error("No candidates in Gemini response")
                        return None
                else:
                    error_text = await response.text()
                    logger.error(f"Gemini API error: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
            return None
    
    def _prepare_image_for_api(self, image_data: bytes) -> Dict[str, Any]:
        """
        Prepare image data for Gemini Vision API.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            dict: Formatted image data for API
        """
        try:
            # Convert to base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            
            # Try to determine format from image data
            try:
                img = Image.open(io.BytesIO(image_data))
                mime_type = f"image/{img.format.lower()}" if img.format else "image/jpeg"
            except Exception:
                mime_type = "image/jpeg"  # Default fallback
            
            return {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": image_b64
                }
            }
            
        except Exception as e:
            logger.error(f"Error preparing image for API: {e}")
            raise
    
    @with_retry(max_retries=3, delay=2.0)
    async def classify_intent(self, message: str):
        """Classify user intent from message text using natural conversation."""
        if not self.api_key or self.api_key == "disabled":
            # Return a simple default result when API is disabled
            return self._fallback_intent_classification(message)
                
        try:
            prompt = GeminiPrompts.get_intent_classification_prompt(message)
            
            response = await self._call_gemini_api(prompt, temperature=0.4)  # Higher temp for better natural understanding
            
            # Return a default object if we couldn't get a response
            if not response:
                return self._fallback_intent_classification(message)
            
            # Try to parse the response into JSON
            try:
                # First try direct parsing
                parsed_json = json.loads(response)
                
                # Map new intent names to old ones for compatibility
                intent_mapping = {
                    "create_task": "create_challenge_intent",
                    "add_money": "add_funds", 
                    "check_balance": "get_balance",
                    "list_tasks": "list_challenges",
                    "task_proof": "submit_completion",
                    "help": "help",
                    "general_chat": "general_chat"
                }
                
                original_intent = parsed_json.get("intent", "general_chat")
                mapped_intent = intent_mapping.get(original_intent, original_intent)
                
                # Extract data and map field names
                extracted_data = parsed_json.get("extracted_data", {})
                
                # Map new field names to old ones
                if "goal" in extracted_data:
                    extracted_data["title"] = extracted_data.pop("goal")
                if "mentioned_amount" in extracted_data:
                    extracted_data["amount"] = extracted_data.pop("mentioned_amount")
                if "timeframe" in extracted_data:
                    extracted_data["deadline"] = extracted_data.pop("timeframe")
                
                # Create a structured result object
                return IntentClassificationResult(
                    intent=mapped_intent,
                    confidence=min(1.0, max(0.0, float(parsed_json.get("confidence", 0.5)))),
                    extracted_data=extracted_data,
                    requires_clarification=parsed_json.get("requires_clarification", False),
                    clarification_question=parsed_json.get("clarification_question", "")
                )
                
            except json.JSONDecodeError:
                # Try to extract JSON from text response
                json_match = re.search(r'({[\s\S]*?})', response)
                if json_match:
                    try:
                        json_str = json_match.group(1)
                        parsed_json = json.loads(json_str)
                        
                        # Apply same mapping logic
                        intent_mapping = {
                            "create_task": "create_challenge_intent",
                            "add_money": "add_funds", 
                            "check_balance": "get_balance",
                            "list_tasks": "list_challenges",
                            "task_proof": "submit_completion",
                            "help": "help",
                            "general_chat": "general_chat"
                        }
                        
                        original_intent = parsed_json.get("intent", "general_chat")
                        mapped_intent = intent_mapping.get(original_intent, original_intent)
                        
                        extracted_data = parsed_json.get("extracted_data", {})
                        if "goal" in extracted_data:
                            extracted_data["title"] = extracted_data.pop("goal")
                        if "mentioned_amount" in extracted_data:
                            extracted_data["amount"] = extracted_data.pop("mentioned_amount")
                        if "timeframe" in extracted_data:
                            extracted_data["deadline"] = extracted_data.pop("timeframe")
                        
                        return IntentClassificationResult(
                            intent=mapped_intent,
                            confidence=min(1.0, max(0.0, float(parsed_json.get("confidence", 0.5)))),
                            extracted_data=extracted_data,
                            requires_clarification=parsed_json.get("requires_clarification", False),
                            clarification_question=parsed_json.get("clarification_question", "")
                        )
                    except json.JSONDecodeError:
                        # If JSON extraction failed, fallback to keyword matching
                        logger.error(f"Failed to parse Gemini response: {json_match.group(1)}")
                
                # If all parsing fails, use improved fallback
                return self._fallback_intent_classification(message)
                
        except Exception as e:
            logger.error(f"Error in intent classification: {e}")
            return self._fallback_intent_classification(message)
    
    @with_retry(max_retries=3, delay=2.0)
    async def verify_image_proof(
        self,
        image_data: bytes,
        challenge_title: str,
        verification_details: str,
        image_description: str = ""
    ) -> Dict[str, Any]:
        """
        Verify image/video proof using Gemini Vision with frontend-matching logic.
        
        Args:
            image_data: Raw image/video bytes
            challenge_title: The challenge being verified
            verification_details: Specific verification requirements
            image_description: Optional description of the image
            
        Returns:
            dict: Verification result matching frontend logic
        """
        if not self.api_key:
            # Fallback verification without AI
            return {
                "verified": False,
                "confidence": 0,
                "analysis": "AI verification unavailable - manual review required",
                "isValid": False
            }
        
        try:
            session = await self._get_session()
            
            # Use frontend-style prompt that focuses on task category relationship
            prompt = f"""
You are an image classification AI. Your job is to check if an image relates to a specific task category.

Task: "{challenge_title}"

IMPORTANT INSTRUCTIONS:
- You only need to check if the image is RELATED to the task category
- You do NOT need to verify active participation or completion
- You do NOT need to check timestamps or dates
- Be LENIENT and HELPFUL to the user

Examples of what to look for:
- For gym/workout tasks: ANY gym environment, gym equipment, fitness area, workout space, gym interior/exterior
- For reading tasks: Books, study materials, library, reading space, educational content
- For cooking tasks: Kitchen, food ingredients, cooking tools, recipes, food preparation area
- For outdoor tasks: Outdoor environments, nature, parks, streets, outdoor activities
- For sleep tasks: Bedroom, bed, sleep tracking apps, alarm clocks
- For study tasks: Study materials, desk setup, educational content, learning environment

Question: Does this image relate to the task category "{challenge_title}"?

Respond ONLY in this exact JSON format:
{{
    "verified": true/false,
    "confidence": number_between_0_and_100,
    "analysis": "brief explanation of what you see and why it relates or doesn't relate to the task category",
    "isValid": true/false
}}
"""
            
            # Prepare image data
            image_part = self._prepare_image_for_api(image_data)
            
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        image_part
                    ]
                }],
                "generationConfig": {
                    "temperature": 0.1,  # Low temperature for consistent results
                    "maxOutputTokens": 500
                }
            }
            
            url = f"{self.base_url}/models/{self.model}:generateContent"
            
            async with session.post(
                url,
                json=payload,
                headers={"x-goog-api-key": self.api_key}
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    
                    if "candidates" in result and result["candidates"]:
                        content = result["candidates"][0]["content"]["parts"][0]["text"]
                        
                        try:
                            # Clean and parse JSON response
                            clean_content = content.replace("```json\n", "").replace("\n```", "").replace("```", "").strip()
                            verification_result = json.loads(clean_content)
                            
                            # Ensure all required fields exist
                            return {
                                "verified": bool(verification_result.get("verified", False)),
                                "confidence": min(100, max(0, int(verification_result.get("confidence", 0)))),
                                "analysis": str(verification_result.get("analysis", "No analysis provided")),
                                "isValid": bool(verification_result.get("isValid", verification_result.get("verified", False)))
                            }
                            
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse image verification response: {e}")
                            logger.error(f"Raw content: {content}")
                            
                            # Try to extract verification from text
                            is_valid = "verified\": true" in content.lower() or "isvalid\": true" in content.lower()
                            return {
                                "verified": is_valid,
                                "confidence": 50,
                                "analysis": f"Parsing failed. Raw: {content[:200]}...",
                                "isValid": is_valid
                            }
                    else:
                        logger.error("No candidates in Gemini image verification response")
                        return {
                            "verified": False,
                            "confidence": 0,
                            "analysis": "AI service returned no results",
                            "isValid": False
                        }
                else:
                    error_text = await response.text()
                    logger.error(f"Gemini image verification API error: {response.status} - {error_text}")
                    return {
                        "verified": False,
                        "confidence": 0,
                        "analysis": f"API error: {response.status}",
                        "isValid": False
                    }
                    
        except Exception as e:
            logger.error(f"Error in image verification: {e}")
            return {
                "verified": False,
                "confidence": 0,
                "analysis": f"Verification failed: {str(e)}",
                "isValid": False
            }

    @with_retry(max_retries=3, delay=2.0)
    async def analyze_image_with_prompt(
        self,
        image_data: bytes,
        prompt: str
    ) -> Dict[str, Any]:
        """
        Analyze image with custom prompt using Gemini Vision.
        
        Args:
            image_data: Raw image bytes
            prompt: Custom prompt for analysis
            
        Returns:
            dict: Analysis result with 'analysis' key containing the response
        """
        if not self.api_key:
            # Fallback response without AI
            return {
                "analysis": "AI analysis unavailable - API key not configured",
                "error": "api_key_missing"
            }
        
        try:
            session = await self._get_session()
            
            # Prepare image data
            image_part = self._prepare_image_for_api(image_data)
            
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        image_part
                    ]
                }],
                "generationConfig": {
                    "temperature": 0.1,  # Low temperature for consistent results
                    "maxOutputTokens": 1000
                }
            }
            
            url = f"{self.base_url}/models/{self.model}:generateContent"
            
            async with session.post(
                url,
                json=payload,
                headers={"x-goog-api-key": self.api_key}
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    
                    if "candidates" in result and result["candidates"]:
                        content = result["candidates"][0]["content"]["parts"][0]["text"]
                        
                        return {
                            "analysis": content,
                            "success": True
                        }
                    else:
                        logger.error("No candidates in Gemini image analysis response")
                        return {
                            "analysis": "AI service returned no results",
                            "error": "no_candidates"
                        }
                else:
                    error_text = await response.text()
                    logger.error(f"Gemini image analysis API error: {response.status} - {error_text}")
                    return {
                        "analysis": f"API error: {response.status} - {error_text}",
                        "error": f"api_error_{response.status}"
                    }
                    
        except Exception as e:
            logger.error(f"Error in image analysis: {e}")
            return {
                "analysis": f"Analysis failed: {str(e)}",
                "error": "exception"
            }
    
    async def verify_payment_screenshot(
        self,
        image_data: bytes,
        expected_amount: float,
        expected_upi_id: str = "devtalele0@okhdfcbank",
        payment_time_window_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Verify UPI payment screenshot using Gemini Vision.
        
        Args:
            image_data: Raw image bytes of the payment screenshot
            expected_amount: Amount user said they would pay
            expected_upi_id: UPI ID they should have paid to
            payment_time_window_hours: How recent the payment should be
            
        Returns:
            dict: Payment verification result with detailed analysis
        """
        if not self.api_key or self.api_key == "disabled":
            # Fallback verification when AI unavailable - be conservative
            return {
                "verified": False,
                "confidence": 0.0,
                "amount_paid": 0.0,
                "recipient_upi": "",
                "transaction_status": "UNKNOWN",
                "timestamp_valid": False,
                "amount_matches": False,
                "upi_matches": False,
                "verdict": "Manual review required - AI verification unavailable",
                "concerns": ["AI verification system unavailable", "Manual verification needed"],
                "suggested_action": "manual_review"
            }
        
        try:
            session = await self._get_session()
            
            prompt = GeminiPrompts.get_payment_verification_prompt(
                expected_amount, expected_upi_id, payment_time_window_hours
            )
            
            # Prepare image for API
            image_part = self._prepare_image_for_api(image_data)
            
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        image_part
                    ]
                }],
                "generationConfig": {
                    "temperature": 0.1,  # Very low temperature for factual verification
                    "maxOutputTokens": 1000,
                    "candidateCount": 1
                }
            }
            
            url = f"{self.base_url}/models/{self.model}:generateContent"
            
            logger.info(f"🤖 Sending payment verification request to Gemini API...")
            
            async with session.post(
                url,
                json=payload,
                headers={"x-goog-api-key": self.api_key}
            ) as response:
                
                response_text = await response.text()
                logger.info(f"🔍 Gemini API response status: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    
                    if "candidates" in result and result["candidates"]:
                        raw_content = result["candidates"][0]["content"]["parts"][0]["text"]
                        logger.info(f"🤖 Raw AI response: {raw_content[:200]}...")
                        
                        # Try to extract JSON from the response (AI might add extra text)
                        verification_result = self._extract_and_parse_json(raw_content)
                        
                        if verification_result:
                            # Enhance the verification result with better logic
                            verification_result = self._enhance_verification_result(
                                verification_result, expected_amount, expected_upi_id
                            )
                            
                            logger.info(f"✅ Payment verification successful: {verification_result.get('suggested_action')}")
                            return verification_result
                        else:
                            logger.error(f"❌ Could not parse JSON from AI response: {raw_content}")
                            return self._create_parsing_error_response()
                    else:
                        logger.error("❌ No candidates in payment verification response")
                        return self._create_api_error_response("No AI response candidates")
                else:
                    logger.error(f"❌ Gemini API error: {response.status} - {response_text[:200]}")
                    return self._create_api_error_response(f"API error {response.status}")
                    
        except Exception as e:
            logger.error(f"❌ Exception in payment verification: {e}")
            import traceback
            traceback.print_exc()
            return self._create_technical_error_response(str(e))
    
    def _extract_and_parse_json(self, raw_content: str) -> Optional[Dict[str, Any]]:
        """Extract and parse JSON from AI response, handling extra text."""
        try:
            # First try direct JSON parsing
            return json.loads(raw_content.strip())
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON within the text
        import re
        
        # Look for JSON blocks between triple backticks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Look for any JSON-like structure
        json_match = re.search(r'\{.*\}', raw_content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        logger.error(f"❌ Could not extract valid JSON from: {raw_content}")
        return None
    
    def _enhance_verification_result(self, result: Dict[str, Any], expected_amount: float, expected_upi_id: str) -> Dict[str, Any]:
        """Enhance verification result with better logic and defaults."""
        # Ensure all required fields exist with defaults
        enhanced = {
            "verified": result.get("verified", False),
            "confidence": float(result.get("confidence", 0.0)),
            "amount_paid": float(result.get("amount_paid", 0.0)),
            "recipient_upi": str(result.get("recipient_upi", "")).strip(),
            "transaction_status": str(result.get("transaction_status", "UNKNOWN")).upper(),
            "timestamp_valid": bool(result.get("timestamp_valid", False)),
            "amount_matches": bool(result.get("amount_matches", False)),
            "upi_matches": bool(result.get("upi_matches", False)),
            "verdict": str(result.get("verdict", "No analysis provided")),
            "concerns": result.get("concerns", []),
            "suggested_action": str(result.get("suggested_action", "manual_review"))
        }
        
        # Improve UPI matching logic
        if enhanced["recipient_upi"]:
            recipient_clean = enhanced["recipient_upi"].lower().strip()
            expected_clean = expected_upi_id.lower().strip()
            
            # Check for exact match or common variations
            if (recipient_clean == expected_clean or 
                recipient_clean in expected_clean or 
                expected_clean in recipient_clean or
                recipient_clean.replace("@", "") == expected_clean.replace("@", "")):
                enhanced["upi_matches"] = True
            
            # Log UPI comparison for debugging
            logger.info(f"🏦 UPI comparison: '{recipient_clean}' vs '{expected_clean}' = {enhanced['upi_matches']}")
        
        # Improve amount matching logic
        amount_diff = abs(enhanced["amount_paid"] - expected_amount)
        amount_diff_percent = (amount_diff / expected_amount) * 100 if expected_amount > 0 else 100
        
        # More flexible amount matching (within 5% or ₹10)
        if amount_diff <= 10 or amount_diff_percent <= 5:
            enhanced["amount_matches"] = True
        
        logger.info(f"💰 Amount comparison: ₹{enhanced['amount_paid']} vs ₹{expected_amount} (diff: ₹{amount_diff}, {amount_diff_percent:.1f}%) = {enhanced['amount_matches']}")
        
        # Improve suggested action logic
        if enhanced["transaction_status"] in ["SUCCESS", "COMPLETED", "DONE"]:
            if enhanced["upi_matches"] and enhanced["timestamp_valid"]:
                if enhanced["amount_paid"] >= expected_amount * 0.8:  # At least 80% of expected
                    # If amount is significantly different (more than 5% difference), use credit_partial to credit actual amount
                    amount_diff_percent = abs(enhanced["amount_paid"] - expected_amount) / expected_amount * 100
                    if amount_diff_percent <= 5:  # Within 5% of expected - very close match
                        enhanced["suggested_action"] = "credit_full"
                    else:
                        # Amount is significantly different - credit the actual amount
                        enhanced["suggested_action"] = "credit_partial"
                else:
                    enhanced["suggested_action"] = "manual_review"
                    enhanced["concerns"].append(f"Amount too low: ₹{enhanced['amount_paid']} vs expected ₹{expected_amount}")
            else:
                if not enhanced["upi_matches"]:
                    enhanced["concerns"].append(f"UPI mismatch: paid to '{enhanced['recipient_upi']}' instead of '{expected_upi_id}'")
                if not enhanced["timestamp_valid"]:
                    enhanced["concerns"].append("Payment timestamp outside acceptable window")
                enhanced["suggested_action"] = "manual_review"
        else:
            enhanced["suggested_action"] = "reject"
            enhanced["concerns"].append(f"Transaction not successful: {enhanced['transaction_status']}")
        
        # Special case: if amount is significantly higher, always allow it and add note
        if enhanced["amount_paid"] > expected_amount * 1.1 and enhanced["upi_matches"] and enhanced["transaction_status"] in ["SUCCESS", "COMPLETED", "DONE"]:
            enhanced["suggested_action"] = "credit_partial"  # Credit actual amount
            enhanced["verdict"] += f" (User paid extra: ₹{enhanced['amount_paid'] - expected_amount:.2f})"
        
        return enhanced
    
    def _create_parsing_error_response(self) -> Dict[str, Any]:
        """Create response for JSON parsing errors."""
        return {
            "verified": False,
            "confidence": 0.0,
            "amount_paid": 0.0,
            "recipient_upi": "",
            "transaction_status": "UNKNOWN",
            "timestamp_valid": False,
            "amount_matches": False,
            "upi_matches": False,
            "verdict": "Could not analyze payment screenshot - AI response format error",
            "concerns": ["AI response parsing failed", "Manual review required"],
            "suggested_action": "manual_review"
        }
    
    def _create_api_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create response for API errors."""
        return {
            "verified": False,
            "confidence": 0.0,
            "amount_paid": 0.0,
            "recipient_upi": "",
            "transaction_status": "UNKNOWN",
            "timestamp_valid": False,
            "amount_matches": False,
            "upi_matches": False,
            "verdict": f"Payment verification failed - {error_message}",
            "concerns": ["AI verification system error"],
            "suggested_action": "manual_review"
        }
    
    def _create_technical_error_response(self, error_details: str) -> Dict[str, Any]:
        """Create response for technical errors."""
        return {
            "verified": False,
            "confidence": 0.0,
            "amount_paid": 0.0,
            "recipient_upi": "",
            "transaction_status": "UNKNOWN",
            "timestamp_valid": False,
            "amount_matches": False,
            "upi_matches": False,
            "verdict": f"Technical error during verification: {error_details[:100]}",
            "concerns": ["Technical error in verification system"],
            "suggested_action": "manual_review"
        }
    
    async def enhance_challenge(self, partial_description: str) -> Dict[str, Any]:
        """
        Enhance challenge description with AI suggestions.
        
        Args:
            partial_description: User's initial challenge description
            
        Returns:
            dict: Enhanced challenge details
        """
        if not self.api_key:
            # Fallback enhancement
            return {
                "improved_title": partial_description,
                "suggested_amount": 100,
                "suggested_deadline": "24 hours",
                "verification_method": "photo",
                "verification_details": "Submit a clear photo as proof of completion",
                "motivational_tip": "You can do this! Stay focused on your goal.",
                "difficulty_level": "medium"
            }
        
        try:
            session = await self._get_session()
            
            prompt = GeminiPrompts.get_challenge_suggestions_prompt(partial_description)
            
            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 600
                }
            }
            
            url = f"{self.base_url}/models/{self.model}:generateContent"
            
            async with session.post(
                url,
                json=payload,
                headers={"x-goog-api-key": self.api_key}
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    
                    if "candidates" in result and result["candidates"]:
                        content = result["candidates"][0]["content"]["parts"][0]["text"]
                        
                        try:
                            return json.loads(content)
                        except json.JSONDecodeError:
                            # Return fallback if parsing fails
                            return {
                                "improved_title": partial_description,
                                "suggested_amount": 100,
                                "suggested_deadline": "24 hours",
                                "verification_method": "photo",
                                "verification_details": "Submit clear proof of completion",
                                "motivational_tip": "Stay committed to your goal!",
                                "difficulty_level": "medium"
                            }
                            
        except Exception as e:
            logger.error(f"Error enhancing challenge: {e}")
            
        # Return fallback enhancement
        return {
            "improved_title": partial_description,
            "suggested_amount": 100,
            "suggested_deadline": "24 hours", 
            "verification_method": "photo",
            "verification_details": "Submit clear proof of completion",
            "motivational_tip": "You've got this! Stay focused.",
            "difficulty_level": "medium"
        }
    
    async def parse_reminder_request(self, reminder_request: str) -> Dict[str, Any]:
        """
        Parse natural language reminder request.
        
        Args:
            reminder_request: User's reminder request
            
        Returns:
            dict: Parsed reminder data
        """
        if not self.api_key:
            # Fallback parsing
            return {
                "reminder_time": None,
                "hours_before_deadline": 2,
                "reminder_type": "deadline",
                "message": "",
                "valid": False,
                "error": "AI parsing unavailable - please use specific format"
            }
        
        try:
            session = await self._get_session()
            
            prompt = GeminiPrompts.get_reminder_parsing_prompt(reminder_request)
            
            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 300
                }
            }
            
            url = f"{self.base_url}/models/{self.model}:generateContent"
            
            async with session.post(
                url,
                json=payload,
                headers={"x-goog-api-key": self.api_key}
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    
                    if "candidates" in result and result["candidates"]:
                        content = result["candidates"][0]["content"]["parts"][0]["text"]
                        
                        try:
                            return json.loads(content)
                        except json.JSONDecodeError:
                            return {
                                "valid": False,
                                "error": "Could not parse reminder request"
                            }
                            
        except Exception as e:
            logger.error(f"Error parsing reminder: {e}")
            
        return {
            "valid": False,
            "error": "Failed to parse reminder request"
        }
    
    async def generate_conversational_response(
        self,
        message: str,
        user_context: Dict[str, Any],
        conversation_history: List[str] = None
    ) -> str:
        """
        Generate natural, human-like conversational response.
        
        Args:
            message: User's message
            user_context: User context and information
            conversation_history: Recent conversation history
            
        Returns:
            str: AI-generated response
        """
        if not self.api_key:
            # Fallback responses that feel human
            if any(word in message.lower() for word in ["hi", "hello", "hey"]):
                return "Hey! 👋 What goal do you want to work on today?"
            elif any(word in message.lower() for word in ["thanks", "thank you"]):
                return "You're welcome! Keep crushing those goals! 💪"
            elif any(word in message.lower() for word in ["help", "what can"]):
                return "Just tell me what you want to achieve - like 'go to gym' or 'study for 2 hours' and I'll help set it up as a challenge! 🎯"
            else:
                return "I'm here to help you achieve your goals! What do you want to work on? 💪"
        
        try:
            prompt = GeminiPrompts.get_conversation_response_prompt(
                message, user_context, conversation_history
            )
            
            response = await self._call_gemini_api(prompt, temperature=0.8)  # Higher temperature for natural conversation
            
            if response:
                # Clean up the response - remove any formal AI language
                response = response.strip()
                
                # Replace formal language with casual alternatives
                response = response.replace("I understand", "Got it")
                response = response.replace("I apologize", "Sorry")
                response = response.replace("Please let me know", "Let me know")
                response = response.replace("I'd be happy to", "I can")
                
                return response
                
        except Exception as e:
            logger.error(f"Error generating response: {e}")
        
        # Improved fallback responses based on context
        balance = user_context.get('balance', 0)
        active_challenges = user_context.get('active_challenges', 0)
        
        # Context-aware fallbacks
        if any(word in message.lower() for word in ["hi", "hello", "hey"]):
            if balance > 0:
                return "Hey! 👋 What goal are you working on today?"
            else:
                return "Hi there! 👋 Ready to start? Type 'add funds' first!"
        
        if any(word in message.lower() for word in ["thanks", "thank you"]):
            return "You got it! 💪"
        
        if any(word in message.lower() for word in ["help", "confused", "don't understand"]):
            return "No worries! Just tell me what you want to achieve - like 'gym today' or 'study for 2 hours' 😊"
        
        # Default encouraging response
        if balance > 0:
            return "What's the goal? 🎯"
        else:
            return "Let's get you started! Type 'add funds' to begin setting challenges 💪"
    
    def _fallback_intent_classification(self, message: str) -> IntentClassificationResult:
        """
        Human-like fallback intent classification - very generous with task creation.
        If someone mentions doing ANYTHING productive, assume it's task creation.
        """
        message_lower = message.lower().strip()
        
        # Helper function to check for action/goal words
        def contains_action_words():
            action_words = [
                # Movement/Exercise
                "gym", "workout", "exercise", "run", "jog", "walk", "swimming", "yoga", "cycling", "sports", "fitness",
                
                # Learning/Work
                "study", "read", "learn", "book", "course", "homework", "work", "project", "assignment", "practice",
                "coding", "programming", "writing", "research", "meeting", "presentation", "report",
                
                # Health/Lifestyle  
                "sleep", "wake", "early", "bed", "diet", "eat", "cooking", "meal", "meditation", "meditate",
                "drinking water", "vitamin", "medicine", "doctor", "dentist",
                
                # Productivity/Personal
                "clean", "organize", "tidy", "laundry", "shopping", "groceries", "call", "email", "reply",
                "finish", "complete", "start", "begin", "do", "make", "get", "go", "stop", "quit", "avoid",
                
                # Skills/Hobbies
                "guitar", "piano", "music", "singing", "drawing", "painting", "art", "photography", "dancing",
                "language", "spanish", "french", "german", "japanese",
                
                # Time indicators (often paired with goals)
                "today", "tomorrow", "tonight", "morning", "evening", "week", "daily", "every day"
            ]
            
            return any(word in message_lower for word in action_words)
        
        # Helper function to check for goal-oriented phrases
        def contains_goal_phrases():
            goal_phrases = [
                "i want to", "i need to", "i should", "i will", "i'm going to", "im going to",
                "want to", "need to", "should", "will", "going to", "gonna", "planning to",
                "have to", "gotta", "must", "trying to", "attempting to", "working on",
                "let me", "lemme", "time to", "ready to"
            ]
            
            return any(phrase in message_lower for phrase in goal_phrases)
        
        # Very clear fund management patterns
        fund_patterns = [
            "add funds", "add money", "deposit money", "top up", "recharge wallet", "fund wallet",
            "add cash", "put money", "add amount", "add ₹", "deposit ₹", "recharge ₹",
            "money to wallet", "fund my", "add to wallet", "increase balance"
        ]
        
        if any(pattern in message_lower for pattern in fund_patterns):
            # Extract amount if mentioned
            amount_match = re.search(r'₹?(\d+)', message)
            extracted_data = {}
            if amount_match:
                extracted_data["amount"] = int(amount_match.group(1))
            
            return IntentClassificationResult(
                intent="add_funds",
                confidence=0.95,
                extracted_data=extracted_data,
                requires_clarification=False,
                clarification_question=""
            )
        
        # Balance checking patterns
        balance_patterns = [
            "balance", "wallet", "how much money", "check balance", "my balance", 
            "wallet balance", "account balance", "funds", "check wallet", "money left"
        ]
        
        if any(pattern in message_lower for pattern in balance_patterns):
            return IntentClassificationResult(
                intent="get_balance",
                confidence=0.9,
                extracted_data={},
                requires_clarification=False,
                clarification_question=""
            )
        
        # Challenge listing patterns
        list_patterns = [
            "my challenges", "my tasks", "list challenges", "show challenges", "view challenges",
            "my bets", "active challenges", "current challenges", "what challenges", "show tasks"
        ]
        
        if any(pattern in message_lower for pattern in list_patterns):
            return IntentClassificationResult(
                intent="list_challenges",
                confidence=0.9,
                extracted_data={},
                requires_clarification=False,
                clarification_question=""
            )
        
        # Help patterns
        help_patterns = [
            "help", "commands", "what can you do", "how does this work", "instructions",
            "guide", "tutorial", "menu", "options", "explain"
        ]
        
        if any(pattern in message_lower for pattern in help_patterns):
            return IntentClassificationResult(
                intent="help",
                confidence=0.9,
                extracted_data={},
                requires_clarification=False,
                clarification_question=""
            )
        
        # Completion/proof submission patterns
        completion_patterns = [
            "done", "completed", "finished", "did it", "here's proof", "proof", "screenshot",
            "i did", "i completed", "i finished", "submit proof", "verification", "verify"
        ]
        
        if any(pattern in message_lower for pattern in completion_patterns):
            return IntentClassificationResult(
                intent="submit_completion",
                confidence=0.8,
                extracted_data={},
                requires_clarification=False,
                clarification_question=""
            )
        
        # Simple greetings and casual chat (but be restrictive)
        simple_greetings = ["hi", "hello", "hey", "thanks", "thank you", "bye", "good morning", "good evening"]
        if (any(greeting in message_lower for greeting in simple_greetings) and 
            len(message.split()) <= 3 and 
            not contains_action_words() and 
            not contains_goal_phrases()):
            
            return IntentClassificationResult(
                intent="general_chat",
                confidence=0.8,
                extracted_data={},
                requires_clarification=False,
                clarification_question=""
            )
        
        # BE VERY GENEROUS WITH TASK CREATION
        # If message contains ANY action words or goal phrases, assume it's task creation
        if contains_action_words() or contains_goal_phrases():
            # Extract any amount mentioned
            amount_match = re.search(r'₹?(\d+)', message)
            extracted_data = {"goal": message}
            if amount_match:
                extracted_data["amount"] = int(amount_match.group(1))
            
            return IntentClassificationResult(
                intent="create_challenge_intent",
                confidence=0.85,
                extracted_data=extracted_data,
                requires_clarification=False,
                clarification_question=""
            )
        
        # Even if no clear patterns, if the message sounds like someone stating what they want to do,
        # lean towards task creation rather than general chat
        if len(message.split()) >= 2:  # More than just one word
            return IntentClassificationResult(
                intent="create_challenge_intent",
                confidence=0.6,
                extracted_data={"goal": message},
                requires_clarification=False,
                clarification_question=""
            )
        
        # Final fallback - general chat with low confidence
        return IntentClassificationResult(
            intent="general_chat",
            confidence=0.4,
            extracted_data={},
            requires_clarification=False,
            clarification_question=""
        ) 