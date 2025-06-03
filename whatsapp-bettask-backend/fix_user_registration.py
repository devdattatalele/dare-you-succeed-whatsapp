#!/usr/bin/env python3
"""
Fix User Registration

Update the existing user profile with email and name to complete registration.
"""

import os

# Set environment variables
os.environ["DEBUG"] = "true"
os.environ["SUPABASE_URL"] = "https://azuslvofwpnqoxdvvpqg.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF6dXNsdm9md3BucW94ZHZ2cHFnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDgwODA5NzUsImV4cCI6MjA2MzY1Njk3NX0.iM7b7opGJWEzsOv1abcvd1cyJ0tWYAKKQCvSL37aApQ"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF6dXNsdm9md3BucW94ZHZ2cHFnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0ODA4MDk3NSwiZXhwIjoyMDYzNjU2OTc1fQ.or1k0fvwJpkMlFFTIhEAfYnvSs-kfEb9xJUXygVeiQg"

from services.supabase_client import SupabaseClient
import json

def fix_user_registration():
    """Fix the user registration by updating missing fields."""
    print("🔧 Fixing User Registration...")
    
    sc = SupabaseClient()
    
    # Update the user with missing email and name
    user_id = "8a677a01-2cf4-48c6-8554-9c4830d392f8"
    
    try:
        # Update user profile
        result = sc.client.table("profiles").update({
            "email": "devtalele0@gmail.com",
            "full_name": "Devdatta Talele"
        }).eq("id", user_id).execute()
        
        print(f"✅ Updated user profile:")
        print(json.dumps(result.data, indent=2))
        
        # Check current user state
        user_result = sc.client.table("profiles").select("*").eq("id", user_id).execute()
        
        if user_result.data:
            user = user_result.data[0]
            print(f"\n👤 Updated User Info:")
            print(f"   ID: {user['id']}")
            print(f"   Phone: {user['phone']}")
            print(f"   Email: {user['email']}")
            print(f"   Name: {user['full_name']}")
            print(f"   Balance: ₹{user['balance']}")
            print(f"   Created: {user['created_at']}")
            
            # Check pending payments
            payments_result = sc.client.table("payment_requests").select("*").eq(
                "user_id", user_id
            ).eq("status", "pending").execute()
            
            pending_payments = payments_result.data or []
            print(f"\n💰 Pending Payments: {len(pending_payments)}")
            
            total_pending = sum(p['amount'] for p in pending_payments)
            print(f"   Total Amount: ₹{total_pending}")
            
            if pending_payments:
                print("   Payment IDs:")
                for payment in pending_payments:
                    print(f"   - {payment['id'][:8]}... (₹{payment['amount']})")
            
            print(f"\n✅ Registration Fixed! User should now be able to:")
            print(f"   - Add funds to wallet")
            print(f"   - View balance")
            print(f"   - Create challenges")
            print(f"   - Access all features")
            
            if pending_payments:
                print(f"\n⚠️  Note: {len(pending_payments)} pending payments found.")
                print(f"   Screenshots may need manual approval for ₹{total_pending} total.")
        
    except Exception as e:
        print(f"❌ Error fixing registration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_user_registration() 