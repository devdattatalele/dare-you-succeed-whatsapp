#!/usr/bin/env python3
"""
Debug script to reproduce the challenge status issue
"""

import asyncio
import os

# Set environment variables
os.environ['DEBUG'] = 'true'
os.environ['SUPABASE_URL'] = 'https://azuslvofwpnqoxdvvpqg.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF6dXNsdm9md3BucW94ZHZ2cHFnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0ODA4MDk3NSwiZXhwIjoyMDYzNjU2OTc1fQ.or1k0fvwJpkMlFFTIhEAfYnvSs-kfEb9xJUXygVeiQg'

async def debug_challenge_status():
    print("=== 🔍 DEBUG CHALLENGE STATUS ISSUE ===")
    
    from services.supabase_client import SupabaseClient
    
    # Initialize client
    client = SupabaseClient()
    
    # Test user
    user_id = '8a677a01-2cf4-48c6-8554-9c4830d392f8'
    
    print(f"\n📱 Debugging challenge status for user: {user_id}")
    
    # Step 1: Get all challenges
    print(f"\n📋 Step 1: Getting ALL challenges...")
    all_challenges = await client.get_user_challenges(user_id, limit=50)
    print(f"Total challenges: {len(all_challenges)}")
    
    active_count = 0
    completed_count = 0
    failed_count = 0
    
    print(f"\n📊 Challenge Status Breakdown:")
    for i, ch in enumerate(all_challenges[:20]):  # Show first 20
        status_emoji = {"active": "🟢", "completed": "✅", "failed": "❌"}.get(ch['status'], "⚪")
        print(f"  {i+1:2d}. {status_emoji} {ch['title'][:30]:<30} | ₹{ch['amount']:<3} | {ch['status']}")
        
        if ch['status'] == 'active':
            active_count += 1
        elif ch['status'] == 'completed':
            completed_count += 1
        elif ch['status'] == 'failed':
            failed_count += 1
    
    print(f"\n📈 Summary:")
    print(f"   🟢 Active: {active_count}")
    print(f"   ✅ Completed: {completed_count}")
    print(f"   ❌ Failed: {failed_count}")
    
    # Step 2: Get only active challenges (what image handler sees)
    print(f"\n🔍 Step 2: Getting ACTIVE challenges only...")
    active_challenges = await client.get_user_challenges(user_id, status="active")
    print(f"Active challenges returned: {len(active_challenges)}")
    
    if len(active_challenges) != active_count:
        print(f"🚨 MISMATCH! Expected {active_count} active, got {len(active_challenges)}")
    
    print(f"\n🎯 Active challenges (what user sees in image handler):")
    for i, ch in enumerate(active_challenges):
        print(f"  {i+1:2d}. {ch['title'][:30]:<30} | ₹{ch['amount']:<3} | {ch['status']}")
    
    # Step 3: Test completing one challenge
    if active_challenges:
        test_challenge = active_challenges[0]
        print(f"\n🧪 Step 3: Testing completion of challenge:")
        print(f"   Challenge: {test_challenge['title']}")
        print(f"   ID: {test_challenge['id']}")
        print(f"   Current Status: {test_challenge['status']}")
        
        # Mark as completed
        print(f"\n✅ Marking challenge as completed...")
        success = await client.update_challenge_status(test_challenge['id'], "completed")
        
        if success:
            print(f"✅ Update returned success")
            
            # Check status immediately
            print(f"\n🔍 Checking status immediately after update...")
            updated_challenges = await client.get_user_challenges(user_id, limit=100)
            updated_challenge = next((c for c in updated_challenges if c["id"] == test_challenge['id']), None)
            
            if updated_challenge:
                print(f"   Status now: {updated_challenge['status']}")
                if updated_challenge['status'] != 'completed':
                    print(f"🚨 ERROR: Status not updated! Still: {updated_challenge['status']}")
            else:
                print(f"🚨 ERROR: Challenge not found after update!")
            
            # Check active challenges again
            print(f"\n🔄 Checking active challenges after completion...")
            new_active = await client.get_user_challenges(user_id, status="active")
            print(f"Active challenges now: {len(new_active)}")
            
            if len(new_active) >= len(active_challenges):
                print(f"🚨 ERROR: Active count didn't decrease! Was {len(active_challenges)}, now {len(new_active)}")
            else:
                print(f"✅ Active count decreased from {len(active_challenges)} to {len(new_active)}")
            
            # Restore status for next test
            await client.update_challenge_status(test_challenge['id'], "active")
            print(f"🔄 Restored challenge status to active")
        else:
            print(f"❌ Update failed!")
    
    print(f"\n✨ **DEBUG COMPLETE!** ✨")

if __name__ == "__main__":
    asyncio.run(debug_challenge_status()) 