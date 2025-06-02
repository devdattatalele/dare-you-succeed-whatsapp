#!/usr/bin/env python3
"""
Process Pending Payments

Manually process the existing pending payments and credit user wallets.
This fixes the issue where payments were made but not credited.
"""

import os
import asyncio

# Set environment variables
os.environ["DEBUG"] = "true"
os.environ["SUPABASE_URL"] = "https://azuslvofwpnqoxdvvpqg.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF6dXNsdm9md3BucW94ZHZ2cHFnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDgwODA5NzUsImV4cCI6MjA2MzY1Njk3NX0.iM7b7opGJWEzsOv1abcvd1cyJ0tWYAKKQCvSL37aApQ"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF6dXNsdm9md3BucW94ZHZ2cHFnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0ODA4MDk3NSwiZXhwIjoyMDYzNjU2OTc1fQ.or1k0fvwJpkMlFFTIhEAfYnvSs-kfEb9xJUXygVeiQg"

from services.supabase_client import SupabaseClient
from datetime import datetime

async def main():
    """Process all pending payments and credit user wallets."""
    print("💳 Processing Pending Payments...")
    
    sb = SupabaseClient()
    
    # Get all pending payments
    print("\n📋 Getting pending payments...")
    result = sb.client.table("payment_requests").select("*").eq("status", "pending").execute()
    pending_payments = result.data
    
    print(f"Found {len(pending_payments)} pending payments")
    
    total_credited = 0
    
    for payment in pending_payments:
        payment_id = payment["id"]
        user_id = payment["user_id"]
        amount = payment["amount"]
        
        print(f"\n💰 Processing payment {payment_id[:8]}... for user {user_id[:8]}...")
        print(f"   Amount: ₹{amount}")
        
        try:
            # Get current balance
            current_balance = await sb.get_user_balance(user_id)
            print(f"   Current balance: ₹{current_balance}")
            
            # Credit wallet
            new_balance = current_balance + amount
            await sb.update_user_balance(user_id, new_balance)
            print(f"   New balance: ₹{new_balance}")
            
            # Record transaction
            await sb.record_transaction(
                user_id=user_id,
                amount=amount,
                transaction_type="deposit",
                description=f"Manual payment processing - Payment ID: {payment_id[:8]}"
            )
            
            # Update payment status
            sb.client.table("payment_requests").update({
                "status": "approved",
                "approved_at": datetime.now().isoformat()
            }).eq("id", payment_id).execute()
            
            print(f"   ✅ Payment processed successfully!")
            total_credited += amount
            
        except Exception as e:
            print(f"   ❌ Error processing payment: {e}")
    
    print(f"\n🎉 Processing complete!")
    print(f"💰 Total amount credited: ₹{total_credited}")
    print(f"📊 Payments processed: {len(pending_payments)}")

if __name__ == "__main__":
    asyncio.run(main()) 