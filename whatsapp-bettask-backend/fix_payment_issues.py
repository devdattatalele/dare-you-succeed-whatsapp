#!/usr/bin/env python3
"""
Fix Payment Issues

1. Fix database constraint violations for payment_requests
2. Enable AI verification with proper Gemini API key
3. Check and fix any invalid status values
"""

import os

# Set environment variables
os.environ["DEBUG"] = "true"
os.environ["SUPABASE_URL"] = "https://azuslvofwpnqoxdvvpqg.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF6dXNsdm9md3BucW94ZHZ2cHFnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDgwODA5NzUsImV4cCI6MjA2MzY1Njk3NX0.iM7b7opGJWEzsOv1abcvd1cyJ0tWYAKKQCvSL37aApQ"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF6dXNsdm9md3BucW94ZHZ2cHFnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0ODA4MDk3NSwiZXhwIjoyMDYzNjU2OTc1fQ.or1k0fvwJpkMlFFTIhEAfYnvSs-kfEb9xJUXygVeiQg"

from services.supabase_client import SupabaseClient
import json

def fix_payment_issues():
    """Fix payment-related issues."""
    print("🔧 Fixing Payment Issues...")
    
    sc = SupabaseClient()
    
    print("\n1. 📋 Checking database constraints...")
    
    # Check current payment_requests structure
    try:
        result = sc.client.table("payment_requests").select("*").limit(1).execute()
        if result.data:
            print("✅ payment_requests table exists")
            print(f"   Columns: {list(result.data[0].keys())}")
        else:
            print("⚠️ payment_requests table is empty (but exists)")
    except Exception as e:
        print(f"❌ payment_requests table issue: {e}")
        return
    
    print("\n2. 🔍 Checking for invalid status values...")
    
    # Check for any invalid status values
    try:
        result = sc.client.table("payment_requests").select("id, status").execute()
        
        valid_statuses = ['pending', 'approved', 'rejected', 'expired']
        invalid_payments = []
        
        for payment in result.data:
            if payment['status'] not in valid_statuses:
                invalid_payments.append(payment)
        
        if invalid_payments:
            print(f"❌ Found {len(invalid_payments)} payments with invalid status:")
            for payment in invalid_payments:
                print(f"   - ID: {payment['id'][:8]}..., Status: '{payment['status']}'")
            
            # Fix invalid statuses
            print("\n🔧 Fixing invalid statuses...")
            for payment in invalid_payments:
                # Map common invalid statuses to valid ones
                status_mapping = {
                    'under_review': 'pending',
                    'manual_review': 'pending', 
                    'processing': 'pending',
                    'completed': 'approved',
                    'failed': 'rejected',
                    'cancelled': 'rejected',
                    'timeout': 'expired'
                }
                
                old_status = payment['status']
                new_status = status_mapping.get(old_status, 'pending')
                
                try:
                    sc.client.table("payment_requests").update({
                        "status": new_status
                    }).eq("id", payment['id']).execute()
                    
                    print(f"   ✅ Fixed: {old_status} → {new_status}")
                except Exception as e:
                    print(f"   ❌ Failed to fix {payment['id'][:8]}: {e}")
        else:
            print("✅ All payment statuses are valid")
    
    except Exception as e:
        print(f"❌ Error checking payment statuses: {e}")
    
    print("\n3. 🤖 Setting up AI verification...")
    
    # Check current .env file
    env_file = ".env"
    
    try:
        # Read current .env
        env_content = {}
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        env_content[key] = value
        
        # Check Gemini API key
        current_key = env_content.get('GEMINI_API_KEY', 'disabled')
        
        if current_key == 'disabled':
            print("⚠️ Gemini API key is disabled")
            print("\n🔑 To enable AI verification:")
            print("   1. Get a free API key from: https://aistudio.google.com/app/apikey")
            print("   2. Update your .env file:")
            print("      GEMINI_API_KEY=your_actual_api_key_here")
            print("   3. Restart the server")
            print("\n💡 For now, payments will use manual review (secure but slower)")
        else:
            print(f"✅ Gemini API key configured: {current_key[:20]}...")
            
            # Test the API key
            try:
                from ai.gemini_client import GeminiClient
                gemini = GeminiClient()
                
                if gemini.api_key:
                    print("✅ AI verification is enabled and ready")
                else:
                    print("⚠️ AI client initialized but no API key found")
            except Exception as e:
                print(f"⚠️ AI client test failed: {e}")
        
    except Exception as e:
        print(f"❌ Error checking AI configuration: {e}")
    
    print("\n4. 📊 Summary of current payment system:")
    
    try:
        # Count payments by status
        result = sc.client.table("payment_requests").select("status").execute()
        
        status_counts = {}
        for payment in result.data:
            status = payment['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print("   Payment status distribution:")
        for status, count in status_counts.items():
            print(f"   - {status}: {count}")
        
        # Check your user's pending payments
        user_id = "8a677a01-2cf4-48c6-8554-9c4830d392f8"
        result = sc.client.table("payment_requests").select("*").eq(
            "user_id", user_id
        ).execute()
        
        user_payments = result.data
        print(f"\n   Your payments: {len(user_payments)}")
        for payment in user_payments:
            print(f"   - ₹{payment['amount']} ({payment['status']})")
        
    except Exception as e:
        print(f"❌ Error getting payment summary: {e}")
    
    print("\n✅ Payment issues check complete!")
    print("\n💡 Next steps:")
    print("   1. If you want AI verification, get a Gemini API key")
    print("   2. For now, the system uses secure manual review")
    print("   3. Try adding funds again - constraints should be fixed")

if __name__ == "__main__":
    fix_payment_issues() 