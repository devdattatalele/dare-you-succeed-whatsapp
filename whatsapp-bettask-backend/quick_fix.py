#!/usr/bin/env python3
"""
Quick Database Fix Script

Directly fix the database schema using Supabase client
"""

import os
from supabase import create_client

# Use your real Supabase credentials
SUPABASE_URL = "https://azuslvofwpnqoxdvvpqg.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF6dXNsdm9md3BucW94ZHZ2cHFnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MTY4Nzk5MDEsImV4cCI6MjAzMjQ1NTkwMX0.xg7_8nqQjdTfyxXmWIm7WjmIqM19DfLaL8RCULfxXGk"

def check_and_fix_schema():
    """Check current schema and provide fix instructions."""
    try:
        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        
        print("🔍 Checking Current Database Schema...")
        print("=" * 60)
        
        # Test 1: Check if profiles table exists and what columns it has
        print("\n📋 Testing profiles table...")
        try:
            result = client.table("profiles").select("*").limit(1).execute()
            if result.data:
                columns = list(result.data[0].keys())
                print(f"   ✅ profiles table exists with columns: {columns}")
                
                if 'phone' not in columns:
                    print("   ❌ MISSING: 'phone' column")
                if 'balance' not in columns:
                    print("   ❌ MISSING: 'balance' column")
            else:
                print("   ✅ profiles table exists but is empty")
                # Try to describe the table structure
                try:
                    result = client.table("profiles").select("id").limit(1).execute()
                    print("   ✅ Has 'id' column")
                except:
                    print("   ❓ Cannot determine structure")
                    
        except Exception as e:
            print(f"   ❌ profiles table error: {e}")
        
        # Test 2: Check phone column specifically
        print("\n📱 Testing phone column...")
        try:
            result = client.table("profiles").select("phone").limit(1).execute()
            print("   ✅ phone column exists!")
        except Exception as e:
            print(f"   ❌ phone column missing: {e}")
        
        # Test 3: Check balance column specifically  
        print("\n💰 Testing balance column...")
        try:
            result = client.table("profiles").select("balance").limit(1).execute()
            print("   ✅ balance column exists!")
        except Exception as e:
            print(f"   ❌ balance column missing: {e}")
        
        # Test 4: Check payment_requests table
        print("\n💳 Testing payment_requests table...")
        try:
            result = client.table("payment_requests").select("*").limit(1).execute()
            print("   ✅ payment_requests table exists!")
        except Exception as e:
            print(f"   ❌ payment_requests table missing: {e}")
        
        print("\n" + "=" * 60)
        print("🔧 WHAT YOU NEED TO DO:")
        print("=" * 60)
        
        print("""
1. OPEN SUPABASE DASHBOARD:
   → Go to https://supabase.com/dashboard
   → Login and select your project
   
2. OPEN SQL EDITOR:
   → Click "SQL Editor" in left sidebar
   → Click "New Query"
   
3. COPY AND PASTE THIS SQL:

-- Add missing columns to profiles table
ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS phone TEXT,
ADD COLUMN IF NOT EXISTS balance DECIMAL(10,2) DEFAULT 0.00;

-- Create payment_requests table
CREATE TABLE IF NOT EXISTS payment_requests (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    payment_method TEXT NOT NULL DEFAULT 'upi',
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

4. CLICK "RUN" BUTTON

5. RESTART YOUR BACKEND:
   → Stop main.py (Ctrl+C)
   → Run: python main.py
   
6. TEST REGISTRATION AGAIN
        """)
        
        print("🎯 After running the SQL, registration should work!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 This confirms you need to run the SQL script manually in Supabase Dashboard!")

if __name__ == "__main__":
    check_and_fix_schema() 