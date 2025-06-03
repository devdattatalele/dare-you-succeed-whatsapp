#!/usr/bin/env python3
"""
Diagnose Database Setup - Check triggers, functions, and permissions
"""

import asyncio
import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.supabase_client import SupabaseClient

async def diagnose_database():
    """Check database setup in detail"""
    
    print("🔍 DATABASE DIAGNOSIS")
    print("=" * 50)
    
    client = SupabaseClient()
    
    print("\n1️⃣ Checking if trigger exists...")
    try:
        # Check trigger exists
        result = client.client.rpc('sql', {
            'query': "SELECT * FROM pg_trigger WHERE tgname = 'on_auth_user_created'"
        }).execute()
        
        if result.data:
            print("✅ Trigger 'on_auth_user_created' EXISTS")
            for trigger in result.data:
                print(f"   Trigger ID: {trigger.get('oid')}")
                print(f"   Table: {trigger.get('tgrelid')}")
        else:
            print("❌ Trigger 'on_auth_user_created' MISSING")
            print("🔧 You need to run the force cleanup SQL script!")
            return False
    except Exception as e:
        print(f"❌ Error checking trigger: {e}")
        return False
    
    print("\n2️⃣ Checking if function exists...")
    try:
        # Check function exists
        result = client.client.rpc('sql', {
            'query': "SELECT * FROM pg_proc WHERE proname = 'handle_new_user'"
        }).execute()
        
        if result.data:
            print("✅ Function 'handle_new_user' EXISTS")
            for func in result.data:
                print(f"   Function OID: {func.get('oid')}")
        else:
            print("❌ Function 'handle_new_user' MISSING")
            print("🔧 You need to run the force cleanup SQL script!")
            return False
    except Exception as e:
        print(f"❌ Error checking function: {e}")
        return False
    
    print("\n3️⃣ Checking RLS policies...")
    try:
        # Check policies on profiles table
        result = client.client.rpc('sql', {
            'query': "SELECT policyname FROM pg_policies WHERE tablename = 'profiles'"
        }).execute()
        
        if result.data:
            print(f"✅ Found {len(result.data)} policies on profiles table:")
            for policy in result.data:
                print(f"   - {policy.get('policyname')}")
        else:
            print("❌ No policies found on profiles table")
    except Exception as e:
        print(f"❌ Error checking policies: {e}")
    
    print("\n4️⃣ Checking table permissions...")
    try:
        # Test if we can insert into profiles directly
        test_profile = {
            "id": "test-id-123",
            "email": "test@example.com",
            "full_name": "Test User",
            "phone": "+1234567890"
        }
        
        # Try to insert
        result = client.client.table("profiles").insert(test_profile).execute()
        
        if result.data:
            print("✅ Can insert into profiles table directly")
            # Clean up test record
            client.client.table("profiles").delete().eq("id", "test-id-123").execute()
        else:
            print("❌ Cannot insert into profiles table")
            
    except Exception as e:
        print(f"❌ Cannot insert into profiles: {e}")
    
    print("\n5️⃣ Manual trigger test...")
    try:
        # Try to manually call the trigger function
        result = client.client.rpc('sql', {
            'query': """
            SELECT handle_new_user() IS NOT NULL as trigger_exists;
            """
        }).execute()
        
        if result.data:
            print("✅ Trigger function can be called manually")
        else:
            print("❌ Trigger function cannot be called")
            
    except Exception as e:
        print(f"❌ Trigger function test failed: {e}")
        print("💡 This suggests the function doesn't exist or has errors")
    
    return True

async def main():
    """Main function"""
    success = await diagnose_database()
    
    if success:
        print("\n🎯 DIAGNOSIS COMPLETE")
        print("\n🔧 NEXT STEPS:")
        print("1. If trigger/function is missing, run the force cleanup SQL script")
        print("2. Check Supabase Auth logs for specific trigger errors")
        print("3. Try registering with a completely different email")
        print("\n📋 SQL Script to run:")
        print("   File: whatsapp-bettask-backend/sql/force_cleanup_and_fix.sql")
        print("   URL: https://supabase.com/dashboard/project/azuslvofwpnqoxdvvpqg/sql/new")
    else:
        print("\n⚠️  Critical database setup issues found")
        print("🔧 Run the force cleanup SQL script immediately")

if __name__ == "__main__":
    asyncio.run(main()) 