"""
AI-based Timestamp Detector

Uses Gemini Vision API to detect visible timestamps, watermarks, or date stamps
in images since WhatsApp strips EXIF metadata.
"""

import logging
import base64
from datetime import datetime, date
from typing import Dict, Any, Tuple
import json

from ai.gemini_client import GeminiClient
from utils.logger import setup_logger

logger = setup_logger(__name__)

class TimestampDetector:
    """AI-based timestamp detection for images."""
    
    def __init__(self):
        """Initialize timestamp detector with Gemini client."""
        self.gemini = GeminiClient()
        logger.info("Timestamp detector initialized")
    
    async def detect_timestamp_in_image(self, image_data: bytes) -> Tuple[bool, Dict[str, Any]]:
        """
        Detect if image has visible timestamp/watermark using AI.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            tuple: (has_timestamp_today, analysis_data)
        """
        try:
            # Convert image to base64 for Gemini API
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Get today's date for comparison
            today = date.today()
            today_str = today.strftime("%Y-%m-%d")
            today_formats = [
                today.strftime("%d/%m/%Y"),
                today.strftime("%m/%d/%Y"), 
                today.strftime("%d-%m-%Y"),
                today.strftime("%m-%d-%Y"),
                today.strftime("%B %d, %Y"),
                today.strftime("%d %B %Y"),
                today.strftime("%d.%m.%Y"),
                today.strftime("%Y/%m/%d")
            ]
            
            prompt = f"""
You are an expert image analyst. Your job is to detect if this image has a visible timestamp, date stamp, or watermark showing today's date.

**Today's date is: {today_str}**

Look for ANY visible text in the image that shows today's date in formats like:
- {today_formats[0]} (DD/MM/YYYY)
- {today_formats[1]} (MM/DD/YYYY)  
- {today_formats[2]} (DD-MM-YYYY)
- {today_formats[3]} (MM-DD-YYYY)
- {today_formats[4]} (Month DD, YYYY)
- {today_formats[5]} (DD Month YYYY)
- {today_formats[6]} (DD.MM.YYYY)
- {today_formats[7]} (YYYY/MM/DD)
- Any other date format

**IMPORTANT INSTRUCTIONS:**
1. Look carefully in ALL corners of the image
2. Check for camera watermarks, timestamps, date stamps
3. Look for any text overlay showing today's date
4. Check photo apps' date stamps
5. Be very thorough - even small text counts

**What to look for:**
- Camera app timestamps (usually in corners)
- Phone watermarks with date/time
- Screenshot timestamps 
- App-generated date stamps
- Manual date annotations
- Any text showing today's date

Respond ONLY in this exact JSON format:
{{
    "has_timestamp": true/false,
    "timestamp_found": "exact text found or null",
    "location": "where found (corner/center/etc) or null", 
    "confidence": number_between_0_and_100,
    "is_today": true/false,
    "date_detected": "date found in YYYY-MM-DD format or null",
    "analysis": "brief explanation of what you found or didn't find"
}}
"""
            
            # Call Gemini Vision API
            result = await self.gemini.analyze_image_with_prompt(image_data, prompt)
            
            if not result or not result.get("analysis"):
                return False, {
                    "error": "AI analysis failed",
                    "has_timestamp": False,
                    "is_today": False,
                    "confidence": 0,
                    "message": "Could not analyze image for timestamp"
                }
            
            # Parse AI response
            try:
                # Try to extract JSON from response
                response_text = result["analysis"]
                
                # Clean response text (remove markdown if present)
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end]
                elif "```" in response_text:
                    response_text = response_text.replace("```", "")
                
                response_text = response_text.strip()
                
                # Parse JSON response
                ai_result = json.loads(response_text)
                
                has_timestamp = ai_result.get("has_timestamp", False)
                is_today = ai_result.get("is_today", False)
                confidence = ai_result.get("confidence", 0)
                
                # Determine if timestamp shows today's date
                valid_today = has_timestamp and is_today and confidence >= 70
                
                analysis_data = {
                    "has_timestamp": has_timestamp,
                    "is_today": is_today,
                    "confidence": confidence,
                    "timestamp_found": ai_result.get("timestamp_found"),
                    "location": ai_result.get("location"),
                    "date_detected": ai_result.get("date_detected"),
                    "analysis": ai_result.get("analysis", ""),
                    "today_date": today_str,
                    "valid": valid_today
                }
                
                if valid_today:
                    analysis_data["message"] = f"✅ Valid timestamp found showing today's date: {ai_result.get('timestamp_found', 'detected')}"
                elif has_timestamp and not is_today:
                    analysis_data["message"] = f"❌ Timestamp found but shows wrong date: {ai_result.get('date_detected', 'unknown date')}"
                elif has_timestamp and confidence < 70:
                    analysis_data["message"] = f"❌ Timestamp unclear or unreadable (confidence: {confidence}%)"
                else:
                    analysis_data["message"] = "❌ No visible timestamp or date stamp found in image"
                
                logger.info(f"Timestamp detection: valid={valid_today}, confidence={confidence}%, found='{ai_result.get('timestamp_found', 'none')}'")
                
                return valid_today, analysis_data
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
                logger.error(f"Raw response: {response_text}")
                
                # Fallback analysis based on text content
                response_lower = response_text.lower()
                has_timestamp = "timestamp" in response_lower or "date" in response_lower
                is_today = any(fmt.lower() in response_lower for fmt in today_formats)
                
                return False, {
                    "error": "JSON parsing failed",
                    "has_timestamp": has_timestamp,
                    "is_today": is_today,
                    "confidence": 30,
                    "message": f"AI analysis unclear. Raw response: {response_text[:200]}...",
                    "raw_response": response_text
                }
            
        except Exception as e:
            logger.error(f"Error in timestamp detection: {e}")
            return False, {
                "error": str(e),
                "has_timestamp": False,
                "is_today": False,
                "confidence": 0,
                "message": f"Error analyzing image: {str(e)}"
            }
    
    def get_timestamp_instructions(self) -> str:
        """Get instructions for users on how to enable timestamp."""
        return """📱 **How to Enable Camera Timestamp:**

**For Android:**
1. Open Camera app
2. Go to Settings ⚙️
3. Find "Watermark" or "Timestamp" option
4. Enable "Date & Time" watermark
5. Take your proof photo

**For iPhone:**
1. Download "Timestamp Camera" app
2. Or use built-in screenshot timestamp
3. Take photo with visible date/time

**Alternative Methods:**
• Screenshot showing date/time
• Photo with phone's time visible
• Use apps like "Camera Timestamp"

**✅ What we need to see:**
• Today's date clearly visible
• Date/time in any corner
• Any format: DD/MM/YYYY, MM/DD/YYYY, etc.

Take a new photo with timestamp enabled! 📸""" 