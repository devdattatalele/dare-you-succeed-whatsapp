"""
Image Utilities

Helper functions for image processing including:
- EXIF data extraction
- Timestamp verification
- Image metadata analysis
"""

import io
import logging
from datetime import datetime, date
from typing import Dict, Any, Optional, Tuple
from PIL import Image
from PIL.ExifTags import TAGS

from utils.logger import setup_logger

logger = setup_logger(__name__)

def extract_image_metadata(image_data: bytes) -> Dict[str, Any]:
    """
    Extract metadata from image including EXIF data.
    
    Args:
        image_data: Raw image bytes
        
    Returns:
        dict: Image metadata including timestamp, camera info, etc.
    """
    try:
        # Open image
        image = Image.open(io.BytesIO(image_data))
        
        metadata = {
            "format": image.format,
            "size": image.size,
            "mode": image.mode,
            "timestamp": None,
            "camera_make": None,
            "camera_model": None,
            "has_exif": False,
            "date_taken": None
        }
        
        # Extract EXIF data
        exif_data = image.getexif()
        
        if exif_data:
            metadata["has_exif"] = True
            
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                
                if tag == "DateTime":
                    try:
                        metadata["timestamp"] = datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                        metadata["date_taken"] = metadata["timestamp"].date()
                    except ValueError:
                        pass
                        
                elif tag == "DateTimeOriginal":
                    try:
                        metadata["timestamp"] = datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                        metadata["date_taken"] = metadata["timestamp"].date()
                    except ValueError:
                        pass
                        
                elif tag == "Make":
                    metadata["camera_make"] = str(value)
                    
                elif tag == "Model":
                    metadata["camera_model"] = str(value)
        
        logger.info(f"Extracted metadata: timestamp={metadata['timestamp']}, size={metadata['size']}")
        return metadata
        
    except Exception as e:
        logger.error(f"Error extracting image metadata: {e}")
        return {
            "format": None,
            "size": None,
            "mode": None,
            "timestamp": None,
            "camera_make": None,
            "camera_model": None,
            "has_exif": False,
            "date_taken": None,
            "error": str(e)
        }

def is_image_taken_today(image_data: bytes) -> Tuple[bool, Dict[str, Any]]:
    """
    Check if image was taken today based on EXIF timestamp.
    
    Args:
        image_data: Raw image bytes
        
    Returns:
        tuple: (is_today, metadata)
    """
    try:
        metadata = extract_image_metadata(image_data)
        
        if not metadata.get("timestamp"):
            return False, {
                "valid": False,
                "reason": "no_timestamp",
                "message": "Image doesn't have timestamp information (EXIF data missing)",
                "metadata": metadata
            }
        
        image_date = metadata["date_taken"]
        today = date.today()
        
        if image_date == today:
            return True, {
                "valid": True,
                "reason": "valid_timestamp",
                "message": f"Image was taken today ({today})",
                "timestamp": metadata["timestamp"],
                "metadata": metadata
            }
        else:
            days_diff = (today - image_date).days
            
            if days_diff > 0:
                return False, {
                    "valid": False,
                    "reason": "old_image",
                    "message": f"Image was taken {days_diff} day(s) ago on {image_date}",
                    "timestamp": metadata["timestamp"],
                    "metadata": metadata
                }
            else:
                return False, {
                    "valid": False,
                    "reason": "future_image",
                    "message": f"Image timestamp is in the future ({image_date})",
                    "timestamp": metadata["timestamp"],
                    "metadata": metadata
                }
                
    except Exception as e:
        logger.error(f"Error checking image timestamp: {e}")
        return False, {
            "valid": False,
            "reason": "error",
            "message": f"Error checking image timestamp: {str(e)}",
            "metadata": {}
        }

def analyze_image_authenticity(image_data: bytes) -> Dict[str, Any]:
    """
    Analyze image for signs of manipulation or screenshots.
    
    Args:
        image_data: Raw image bytes
        
    Returns:
        dict: Authenticity analysis
    """
    try:
        metadata = extract_image_metadata(image_data)
        
        authenticity_score = 100  # Start with perfect score
        issues = []
        
        # Check for EXIF data
        if not metadata.get("has_exif"):
            authenticity_score -= 30
            issues.append("Missing EXIF data (possible screenshot or edited image)")
        
        # Check image size for typical screenshot resolutions
        if metadata.get("size"):
            width, height = metadata["size"]
            
            # Common screenshot resolutions
            screenshot_resolutions = [
                (1080, 1920), (1080, 2340), (1125, 2436), (828, 1792),
                (1440, 2960), (1440, 3040), (1080, 2400)
            ]
            
            if (width, height) in screenshot_resolutions or (height, width) in screenshot_resolutions:
                authenticity_score -= 25
                issues.append(f"Image resolution ({width}x{height}) matches common screenshot sizes")
        
        # Check camera information
        if not metadata.get("camera_make") and not metadata.get("camera_model"):
            authenticity_score -= 20
            issues.append("No camera information found")
        
        # Determine authenticity level
        if authenticity_score >= 80:
            level = "high"
        elif authenticity_score >= 60:
            level = "medium"
        elif authenticity_score >= 40:
            level = "low"
        else:
            level = "very_low"
        
        return {
            "authenticity_score": authenticity_score,
            "authenticity_level": level,
            "issues": issues,
            "metadata": metadata,
            "is_likely_original": authenticity_score >= 60
        }
        
    except Exception as e:
        logger.error(f"Error analyzing image authenticity: {e}")
        return {
            "authenticity_score": 0,
            "authenticity_level": "unknown",
            "issues": [f"Error analyzing image: {str(e)}"],
            "metadata": {},
            "is_likely_original": False
        } 