#!/usr/bin/env python3
"""
Check if user already exists and debug the registration issue
"""

import asyncio
import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.supabase_client import SupabaseClient

async def check_user_exists():
    """Check if the user test@gmail.com already exists"""
    
    print("🔍 Checking user registration issue...")
    print("=" * 50)
    
    client = SupabaseClient()
    
    # Check if test@gmail.com already exists
    print("\n1️⃣ Checking if test@gmail.com already exists...")
    try:
        existing_user = await client.get_user_by_email("test@gmail.com")
        if existing_user:
            print(f"❌ Email test@gmail.com ALREADY EXISTS!")
            print(f"   User ID: {existing_user.get('id')}")
            print(f"   Phone: {existing_user.get('phone')}")
            print(f"   Name: {existing_user.get('full_name')}")
            print(f"   Created: {existing_user.get('created_at')}")
            print("\n💡 This is why registration is failing!")
            print("🔧 Try with a different email address")
            return False
        else:
            print("✅ Email test@gmail.com is available")
    except Exception as e:
        print(f"❌ Error checking email: {e}")
        return False
    
    # Check if phone number already exists
    print("\n2️⃣ Checking if phone 919370091896 already exists...")
    try:
        existing_phone = await client.get_user_by_phone("919370091896")
        if existing_phone:
            print(f"❌ Phone 919370091896 ALREADY EXISTS!")
            print(f"   User ID: {existing_phone.get('id')}")
            print(f"   Email: {existing_phone.get('email')}")
            print(f"   Name: {existing_phone.get('full_name')}")
            print(f"   Created: {existing_phone.get('created_at')}")
            print("\n💡 This phone is already registered!")
            return False
        else:
            print("✅ Phone 919370091896 is available")
    except Exception as e:
        print(f"❌ Error checking phone: {e}")
        return False
    
    # Try with a unique email
    print("\n3️⃣ Testing with a unique email...")
    unique_email = f"test_{int(asyncio.get_event_loop().time())}@gmail.com"
    unique_phone = "+919999888777"
    
    try:
        user_data = await client.create_auth_user(
            email=unique_email,
            password="TestPassword123",
            full_name="Test User",
            phone=unique_phone
        )
        print(f"✅ SUCCESS! Created user with unique email")
        print(f"   User ID: {user_data['id']}")
        print(f"   Email: {user_data['email']}")
        
        # Check if profile was created
        profile = await client.get_user_by_email(unique_email)
        if profile:
            print(f"✅ Profile automatically created via trigger!")
            print(f"   Profile ID: {profile['id']}")
        else:
            print(f"❌ Profile was NOT created - trigger not working")
        
        return True
        
    except Exception as e:
        print(f"❌ Registration still failing: {e}")
        return False

async def main():
    success = await check_user_exists()
    
    if success:
        print("\n🎉 Database setup is working!")
        print("💡 The issue was duplicate email/phone")
        print("🔧 Use different email/phone for WhatsApp registration")
    else:
        print("\n⚠️  There's still an issue with the database setup")
        print("🔧 Check Supabase logs for more details")

if __name__ == "__main__":
    asyncio.run(main()) 