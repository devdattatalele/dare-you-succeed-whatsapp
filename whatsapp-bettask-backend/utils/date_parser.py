"""
Natural language date and time parsing utility.

Converts human-readable date/time expressions into datetime objects.
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

from utils.logger import setup_logger

logger = setup_logger(__name__)

def parse_natural_date(date_string: str) -> datetime:
    """
    Parse natural language date/time expressions.
    
    Args:
        date_string: Natural language date expression
        
    Returns:
        datetime: Parsed datetime object
        
    Raises:
        ValueError: If the date string cannot be parsed
    """
    date_string = date_string.lower().strip()
    now = datetime.now()
    
    # Remove common words
    date_string = re.sub(r'\b(at|on|by|in|the|a|an)\b', '', date_string).strip()
    
    # Relative time expressions
    relative_patterns = {
        r'(\d+)\s*hour?s?\s*(?:from\s+now)?': lambda m: now + timedelta(hours=int(m.group(1))),
        r'(\d+)\s*minute?s?\s*(?:from\s+now)?': lambda m: now + timedelta(minutes=int(m.group(1))),
        r'(\d+)\s*day?s?\s*(?:from\s+now)?': lambda m: now + timedelta(days=int(m.group(1))),
        r'(\d+)\s*week?s?\s*(?:from\s+now)?': lambda m: now + timedelta(weeks=int(m.group(1))),
        r'(\d+)h': lambda m: now + timedelta(hours=int(m.group(1))),
        r'(\d+)m': lambda m: now + timedelta(minutes=int(m.group(1))),
        r'(\d+)d': lambda m: now + timedelta(days=int(m.group(1))),
    }
    
    for pattern, calculator in relative_patterns.items():
        match = re.search(pattern, date_string)
        if match:
            return calculator(match)
    
    # Named time periods
    if 'tomorrow' in date_string:
        base_date = now + timedelta(days=1)
        # Check for specific time
        time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', date_string)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            ampm = time_match.group(3)
            
            if ampm == 'pm' and hour != 12:
                hour += 12
            elif ampm == 'am' and hour == 12:
                hour = 0
            
            return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            # Default to 9 PM tomorrow
            return base_date.replace(hour=21, minute=0, second=0, microsecond=0)
    
    if 'today' in date_string:
        base_date = now
        # Check for specific time
        time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', date_string)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            ampm = time_match.group(3)
            
            if ampm == 'pm' and hour != 12:
                hour += 12
            elif ampm == 'am' and hour == 12:
                hour = 0
            
            target_time = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            # If the time has passed today, assume tomorrow
            if target_time <= now:
                target_time += timedelta(days=1)
            return target_time
        else:
            # Default to end of day
            return base_date.replace(hour=23, minute=59, second=0, microsecond=0)
    
    if 'tonight' in date_string:
        return now.replace(hour=23, minute=0, second=0, microsecond=0)
    
    if 'next week' in date_string:
        days_ahead = 7 - now.weekday()
        return now + timedelta(days=days_ahead, hours=24-now.hour)
    
    # Day names
    day_names = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6,
        'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6
    }
    
    for day_name, day_num in day_names.items():
        if day_name in date_string:
            days_ahead = (day_num - now.weekday()) % 7
            if days_ahead == 0:  # If it's today, assume next week
                days_ahead = 7
            target_date = now + timedelta(days=days_ahead)
            
            # Check for specific time
            time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', date_string)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                ampm = time_match.group(3)
                
                if ampm == 'pm' and hour != 12:
                    hour += 12
                elif ampm == 'am' and hour == 12:
                    hour = 0
                
                return target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            else:
                return target_date.replace(hour=21, minute=0, second=0, microsecond=0)
    
    # Specific time today/tonight
    time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', date_string)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        ampm = time_match.group(3)
        
        if ampm == 'pm' and hour != 12:
            hour += 12
        elif ampm == 'am' and hour == 12:
            hour = 0
        
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # If the time has passed today, assume tomorrow
        if target_time <= now:
            target_time += timedelta(days=1)
        return target_time
    
    # Default time periods
    if any(word in date_string for word in ['morning', 'am']):
        return (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    
    if any(word in date_string for word in ['afternoon', 'evening']):
        return (now + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
    
    if any(word in date_string for word in ['night', 'pm']):
        return (now + timedelta(days=1)).replace(hour=21, minute=0, second=0, microsecond=0)
    
    # If nothing matches, default to 24 hours from now
    logger.warning(f"Could not parse date string '{date_string}', defaulting to 24 hours from now")
    return now + timedelta(hours=24)

def format_time_remaining(target_time: datetime) -> str:
    """
    Format time remaining until target time in human-readable format.
    
    Args:
        target_time: Target datetime
        
    Returns:
        str: Human-readable time remaining
    """
    now = datetime.now()
    time_diff = target_time - now
    
    if time_diff.total_seconds() <= 0:
        return "Time's up!"
    
    days = time_diff.days
    hours, remainder = divmod(time_diff.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0 and days == 0:  # Only show minutes if less than a day
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    
    if not parts:
        return "Less than a minute"
    
    return " and ".join(parts)

def is_past_deadline(deadline: datetime) -> bool:
    """
    Check if a deadline has passed.
    
    Args:
        deadline: Deadline datetime
        
    Returns:
        bool: True if deadline has passed
    """
    return datetime.now() > deadline

def get_reminder_time(deadline: datetime, hours_before: int = 2) -> Optional[datetime]:
    """
    Calculate reminder time before deadline.
    
    Args:
        deadline: Challenge deadline
        hours_before: Hours before deadline to send reminder
        
    Returns:
        Optional[datetime]: Reminder time, or None if deadline is too soon
    """
    reminder_time = deadline - timedelta(hours=hours_before)
    
    # Don't create reminders for past times
    if reminder_time <= datetime.now():
        return None
    
    return reminder_time

# Common time period mappings
TIME_PERIODS = {
    'hour': timedelta(hours=1),
    'hours': timedelta(hours=1),
    'day': timedelta(days=1),
    'days': timedelta(days=1),
    'week': timedelta(weeks=1),
    'weeks': timedelta(weeks=1),
    'month': timedelta(days=30),
    'months': timedelta(days=30),
} 