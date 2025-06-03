#!/usr/bin/env python3
"""
Database Schema Inspector

Check what tables and columns actually exist in the Supabase database
"""

import os
from supabase import create_client

# Set environment variables
os.environ["SUPABASE_URL"] = "https://azuslvofwpnqoxdvvpqg.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF6dXNsdm9md3BucW94ZHZ2cHFnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MTY4Nzk5MDEsImV4cCI6MjAzMjQ1NTkwMX0.xg7_8nqQjdTfyxXmWIm7WjmIqM19DfLaL8RCULfxXGk"

def inspect_database():
    """Inspect the current database schema."""
    try:
        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_ANON_KEY"]
        )
        
        print("🔍 Inspecting Database Schema...")
        print("=" * 50)
        
        # Check what tables exist
        tables_to_check = ["profiles", "challenges", "wallets", "transactions", "payment_requests"]
        
        for table_name in tables_to_check:
            print(f"\n📋 Table: {table_name}")
            try:
                # Try to get one record to see the schema
                result = client.table(table_name).select("*").limit(1).execute()
                
                if result.data:
                    # Show columns from the first record
                    columns = list(result.data[0].keys())
                    print(f"   ✅ Exists with columns: {', '.join(columns)}")
                else:
                    # Table exists but is empty, try to describe it
                    print(f"   ✅ Exists but is empty")
                    
            except Exception as e:
                error_msg = str(e)
                if "does not exist" in error_msg or "relation" in error_msg:
                    print(f"   ❌ Does not exist")
                elif "column" in error_msg and "does not exist" in error_msg:
                    print(f"   ⚠️  Table exists but has schema issues: {error_msg}")
                else:
                    print(f"   ❓ Error: {error_msg}")
        
        # Check if we can access the auth.users table
        print(f"\n👤 Auth Users:")
        try:
            # This might not work with anon key, but worth trying
            result = client.auth.admin.list_users()
            print(f"   ✅ Can access auth users")
        except Exception as e:
            print(f"   ❌ Cannot access: {e}")
        
        # Test specific queries that are failing
        print(f"\n🧪 Testing Problem Queries:")
        
        # Test 1: profiles with phone column
        try:
            result = client.table("profiles").select("phone").limit(1).execute()
            print("   ✅ profiles.phone column exists")
        except Exception as e:
            print(f"   ❌ profiles.phone: {e}")
        
        # Test 2: profiles with balance column  
        try:
            result = client.table("profiles").select("balance").limit(1).execute()
            print("   ✅ profiles.balance column exists")
        except Exception as e:
            print(f"   ❌ profiles.balance: {e}")
        
        # Test 3: Check auth schema
        try:
            result = client.table("profiles").select("id").limit(1).execute()
            print("   ✅ profiles.id column exists")
        except Exception as e:
            print(f"   ❌ profiles.id: {e}")
            
        print(f"\n💡 Recommendations:")
        print("1. If profiles table is missing columns, run the SQL fix below")
        print("2. If tables don't exist, create them with the provided SQL")
        print("3. Check if you're using Supabase Auth vs custom user system")
        
    except Exception as e:
        print(f"❌ Failed to inspect database: {e}")

def generate_fix_sql():
    """Generate SQL to fix the schema issues."""
    print(f"\n🔧 SQL Fix Commands:")
    print("=" * 50)
    
    print("""
-- Option 1: Add missing columns to existing profiles table
ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS phone TEXT,
ADD COLUMN IF NOT EXISTS balance DECIMAL(10,2) DEFAULT 0.00;

-- Create index for phone lookups
CREATE INDEX IF NOT EXISTS idx_profiles_phone ON profiles(phone);

-- Option 2: Create profiles table if it doesn't exist
CREATE TABLE IF NOT EXISTS profiles (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    phone TEXT UNIQUE,
    balance DECIMAL(10,2) DEFAULT 0.00,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create the payment_requests table
CREATE TABLE IF NOT EXISTS payment_requests (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    payment_method TEXT NOT NULL DEFAULT 'upi',
    metadata JSONB,
    screenshot_url TEXT,
    screenshot_uploaded_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

-- Create wallets table
CREATE TABLE IF NOT EXISTS wallets (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL,
    balance DECIMAL(10,2) DEFAULT 0.00,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
""")

if __name__ == "__main__":
    inspect_database()
    generate_fix_sql() 