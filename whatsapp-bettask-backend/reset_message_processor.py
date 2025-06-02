#!/usr/bin/env python3
"""
Reset Message Processor Utility

Use this script to:
1. Stop message spam by clearing the processed timestamp
2. Set a new "last processed" time to avoid reprocessing old messages
3. Clear the message processing cache
"""

import os
import sqlite3
from datetime import datetime, timedelta
import argparse

LAST_PROCESSED_FILE = "last_processed_timestamp.txt"
MCP_DB_PATH = "/Users/dev16/Documents/Test project/dare-you-succeed 3/whatsapp-mcp/whatsapp-bridge/store/messages.db"

def reset_to_current_time():
    """Reset the last processed timestamp to current time."""
    current_time = datetime.now()
    
    try:
        with open(LAST_PROCESSED_FILE, 'w') as f:
            f.write(current_time.isoformat())
        print(f"✅ Reset last processed time to: {current_time}")
        print("   This will prevent processing any existing messages.")
    except Exception as e:
        print(f"❌ Error resetting timestamp: {e}")

def reset_to_specific_time(hours_ago: int):
    """Reset to a specific number of hours ago."""
    target_time = datetime.now() - timedelta(hours=hours_ago)
    
    try:
        with open(LAST_PROCESSED_FILE, 'w') as f:
            f.write(target_time.isoformat())
        print(f"✅ Reset last processed time to: {target_time}")
        print(f"   This will process messages from the last {hours_ago} hours.")
    except Exception as e:
        print(f"❌ Error resetting timestamp: {e}")

def show_current_status():
    """Show current system status."""
    print("=== WhatsApp BetTask Message Processor Status ===")
    
    # Check last processed time
    if os.path.exists(LAST_PROCESSED_FILE):
        try:
            with open(LAST_PROCESSED_FILE, 'r') as f:
                timestamp_str = f.read().strip()
                last_time = datetime.fromisoformat(timestamp_str)
            print(f"Last processed time: {last_time}")
            print(f"Time since last process: {datetime.now() - last_time}")
        except Exception as e:
            print(f"❌ Error reading timestamp file: {e}")
    else:
        print("⚠️ No timestamp file found (first run)")
    
    # Check MCP database
    if os.path.exists(MCP_DB_PATH):
        try:
            conn = sqlite3.connect(MCP_DB_PATH)
            cursor = conn.cursor()
            
            # Count total messages
            cursor.execute("SELECT COUNT(*) FROM messages")
            total_messages = cursor.fetchone()[0]
            
            # Count recent messages (last 24 hours)
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("SELECT COUNT(*) FROM messages WHERE timestamp > ?", (yesterday,))
            recent_messages = cursor.fetchone()[0]
            
            # Get latest message
            cursor.execute("SELECT timestamp, sender, content FROM messages ORDER BY timestamp DESC LIMIT 1")
            latest = cursor.fetchone()
            
            print(f"\nMCP Database Status:")
            print(f"  Total messages: {total_messages}")
            print(f"  Recent messages (24h): {recent_messages}")
            if latest:
                print(f"  Latest message: {latest[0]} from {latest[1]}: {latest[2][:50]}...")
            
            conn.close()
        except Exception as e:
            print(f"❌ Error reading MCP database: {e}")
    else:
        print("❌ MCP database not found")

def clear_old_messages():
    """Clear old messages from MCP database (older than 7 days)."""
    if not os.path.exists(MCP_DB_PATH):
        print("❌ MCP database not found")
        return
    
    try:
        conn = sqlite3.connect(MCP_DB_PATH)
        cursor = conn.cursor()
        
        # Delete messages older than 7 days
        cutoff_time = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("SELECT COUNT(*) FROM messages WHERE timestamp < ?", (cutoff_time,))
        old_count = cursor.fetchone()[0]
        
        if old_count > 0:
            cursor.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff_time,))
            conn.commit()
            print(f"✅ Deleted {old_count} old messages (older than 7 days)")
        else:
            print("✅ No old messages to delete")
        
        conn.close()
    except Exception as e:
        print(f"❌ Error clearing old messages: {e}")

def main():
    parser = argparse.ArgumentParser(description="Reset WhatsApp BetTask Message Processor")
    parser.add_argument("--reset-now", action="store_true", 
                       help="Reset to current time (stops all message processing)")
    parser.add_argument("--reset-hours", type=int, metavar="HOURS",
                       help="Reset to X hours ago (processes recent messages)")
    parser.add_argument("--status", action="store_true",
                       help="Show current system status")
    parser.add_argument("--clear-old", action="store_true",
                       help="Clear messages older than 7 days")
    
    args = parser.parse_args()
    
    if args.status:
        show_current_status()
    elif args.reset_now:
        reset_to_current_time()
    elif args.reset_hours:
        reset_to_specific_time(args.reset_hours)
    elif args.clear_old:
        clear_old_messages()
    else:
        # Default action - show status and reset to current time
        print("🛑 STOPPING MESSAGE SPAM")
        print("Resetting to current time to prevent processing old messages...\n")
        show_current_status()
        print("\n" + "="*50)
        reset_to_current_time()
        print("\n✅ Message spam should now be stopped!")
        print("   You can safely restart the backend with: python main.py")

if __name__ == "__main__":
    main() 