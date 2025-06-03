#!/usr/bin/env python3

import asyncio
from services.supabase_client import SupabaseClient

async def check_profiles():
    client = SupabaseClient()
    result = client.client.table('profiles').select('*').execute()
    print('Available profiles:')
    for profile in result.data:
        print(f'ID: {profile["id"]}, email: {profile.get("email")}, phone: {profile.get("phone")}')

if __name__ == "__main__":
    asyncio.run(check_profiles()) 