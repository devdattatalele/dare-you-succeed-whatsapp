#!/usr/bin/env python3
import os, asyncio

os.environ['DEBUG'] = 'true'
os.environ['SUPABASE_URL'] = 'https://azuslvofwpnqoxdvvpqg.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF6dXNsdm9md3BucW94ZHZ2cHFnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0ODA4MDk3NSwiZXhwIjoyMDYzNjU2OTc1fQ.or1k0fvwJpkMlFFTIhEAfYnvSs-kfEb9xJUXygVeiQg'

async def check_challenges():
    from services.supabase_client import SupabaseClient
    client = SupabaseClient()
    user_id = '8a677a01-2cf4-48c6-8554-9c4830d392f8'
    challenges = await client.get_user_challenges(user_id, limit=5)
    print(f'Found {len(challenges)} challenges for user:')
    for c in challenges:
        print(f'  {c["id"][:8]}... - {c["title"]} - ₹{c["amount"]} - {c["status"]} - {c["created_at"]}')
    balance = await client.get_user_balance(user_id)
    print(f'Current balance: ₹{balance}')

asyncio.run(check_challenges()) 