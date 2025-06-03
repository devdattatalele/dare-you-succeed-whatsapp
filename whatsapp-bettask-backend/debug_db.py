#!/usr/bin/env python3
"""
Debug Database Structure

Check current database state and identify issues.
"""

import os
import asyncio

# Set environment variables
os.environ["DEBUG"] = "true"
os.environ["SUPABASE_URL"] = "https://azuslvofwpnqoxdvvpqg.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF6dXNsdm9md3BucW94ZHZ2cHFnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDgwODA5NzUsImV4cCI6MjA2MzY1Njk3NX0.iM7b7opGJWEzsOv1abcvd1cyJ0tWYAKKQCvSL37aApQ"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF6dXNsdm9md3BucW94ZHZ2cHFnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0ODA4MDk3NSwiZXhwIjoyMDYzNjU2OTc1fQ.or1k0fvwJpkMlFFTIhEAfYnvSs-kfEb9xJUXygVeiQg"

from services.supabase_client import SupabaseClient

def main():
    """Debug database issues."""
    print("🔍 Debugging Database Issues...")
    
    sb = SupabaseClient()
    
    # Check profiles table structure
    print("\n📋 PROFILES TABLE:")
    try:
        result = sb.client.table("profiles").select("*").limit(1).execute()
        if result.data:
            print("Columns:", list(result.data[0].keys()))
        else:
            print("Table exists, no data")
    except Exception as e:
        print("Error:", str(e))
    
    # Check payment_requests table  
    print("\n💳 PAYMENT_REQUESTS TABLE:")
    try:
        result = sb.client.table("payment_requests").select("*").limit(1).execute() 
        if result.data:
            print("Columns:", list(result.data[0].keys()))
        else:
            print("Table exists, no data")
    except Exception as e:
        print("Error:", str(e))
    
    # Check specific user
    print("\n👤 USER 919370091896:")
    try:
        result = sb.client.table("profiles").select("*").eq("phone", "919370091896").execute()
        if result.data:
            user = result.data[0]
            print(f"ID: {user['id']}")
            print(f"Phone: {user.get('phone', 'NULL')}")
            print(f"Email: {user.get('email', 'NULL')}") 
            print(f"Balance: {user.get('balance', 'NULL')}")
            print(f"Created: {user.get('created_at', 'NULL')}")
        else:
            print("User not found")
    except Exception as e:
        print("Error:", str(e))
    
    # Check all users
    print("\n👥 ALL USERS:")
    try:
        result = sb.client.table("profiles").select("*").execute()
        print(f"Total users: {len(result.data)}")
        for i, user in enumerate(result.data):
            print(f"{i+1}. Phone: {user.get('phone', 'NULL')}, Balance: {user.get('balance', 0)}")
    except Exception as e:
        print("Error:", str(e))
    
    # Check pending payments
    print("\n💰 PENDING PAYMENTS:")
    try:
        result = sb.client.table("payment_requests").select("*").eq("status", "pending").execute()
        print(f"Pending payments: {len(result.data)}")
        for payment in result.data:
            print(f"- ID: {payment['id'][:8]}..., Amount: ₹{payment['amount']}, User: {payment['user_id'][:8]}...")
    except Exception as e:
        print("Error:", str(e))

if __name__ == "__main__":
    main() 