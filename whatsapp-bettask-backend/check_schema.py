#!/usr/bin/env python3
import asyncio
import os

os.environ['DEBUG'] = 'true'
os.environ['SUPABASE_URL'] = 'https://azuslvofwpnqoxdvvpqg.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF6dXNsdm9md3BucW94ZHZ2cHFnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0ODA4MDk3NSwiZXhwIjoyMDYzNjU2OTc1fQ.or1k0fvwJpkMlFFTIhEAfYnvSs-kfEb9xJUXygVeiQg'

async def check_schema():
    from services.supabase_client import SupabaseClient
    client = SupabaseClient()
    
    print("=== Checking Database Schema ===")
    
    # Check profiles table
    try:
        result = client.client.table('profiles').select('*').limit(1).execute()
        if result.data:
            print('✅ Profiles table columns:', list(result.data[0].keys()))
        else:
            print('⚠️ Profiles table exists but is empty')
    except Exception as e:
        print(f'❌ Profiles table error: {e}')
    
    # Check wallets table
    try:
        result = client.client.table('wallets').select('*').limit(1).execute()
        if result.data:
            print('✅ Wallets table columns:', list(result.data[0].keys()))
        else:
            print('⚠️ Wallets table exists but is empty')
    except Exception as e:
        print(f'❌ Wallets table error: {e}')
    
    # Check payment_requests table
    try:
        result = client.client.table('payment_requests').select('*').limit(1).execute()
        if result.data:
            print('✅ Payment_requests table columns:', list(result.data[0].keys()))
        else:
            print('⚠️ Payment_requests table exists but is empty')
    except Exception as e:
        print(f'❌ Payment_requests table error: {e}')

asyncio.run(check_schema()) 