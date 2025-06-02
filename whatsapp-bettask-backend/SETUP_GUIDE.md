# BetTask WhatsApp Backend Setup Guide

## Quick Fix for Registration Issues

The user registration is failing because of a missing database table. Here's how to fix it:

### 1. Create the Missing Payment Table

Run this SQL in your Supabase SQL editor:

```sql
-- Create payment_requests table for handling UPI payments and registration
CREATE TABLE IF NOT EXISTS payment_requests (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'expired')),
    payment_method TEXT NOT NULL DEFAULT 'upi',
    metadata JSONB,
    screenshot_url TEXT,
    screenshot_uploaded_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_payment_requests_user_id ON payment_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_requests_status ON payment_requests(status);
CREATE INDEX IF NOT EXISTS idx_payment_requests_created_at ON payment_requests(created_at);
```

### 2. Create Storage Bucket for Payment Screenshots

In Supabase Storage, create a bucket called `payment-proofs`:

1. Go to Storage in your Supabase dashboard
2. Click "Create Bucket"
3. Name: `payment-proofs`
4. Make it private (not public)
5. Click "Create Bucket"

### 3. Check Your Environment Variables

Make sure you have the correct Supabase credentials in your `.env.local` file:

```env
SUPABASE_URL=https://azuslvofwpnqoxdvvpqg.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
GEMINI_API_KEY=your_gemini_api_key_here
WHATSAPP_MCP_BRIDGE_URL=http://localhost:8080
WHATSAPP_MCP_DATABASE_PATH='/Users/dev16/Documents/Test project/dare-you-succeed 3/whatsapp-mcp/whatsapp-bridge/store/messages.db'
```

### 4. Restart the Backend

After creating the table and bucket:

1. Stop the backend if it's running (Ctrl+C)
2. Run: `python main.py`
3. Test registration again

## What Was Fixed

The registration handler was trying to create profiles with columns that didn't exist in your database. The updated version:

✅ **Fixed**: Uses the existing simple profiles schema (phone, balance, created_at)
✅ **Fixed**: Stores additional registration info (email) in payment_requests table
✅ **Fixed**: Handles "I already have an account" responses
✅ **Fixed**: Better error handling and cleanup
✅ **Fixed**: Proper registration state management

## Testing Registration

Try these WhatsApp messages:

1. **New User**: Send "start" or "register"
2. **Existing User**: Send "I already have an account"
3. **Follow the prompts** for email, password, and initial amount

## Common Issues

### "Error creating account"
- **Cause**: Missing payment_requests table
- **Fix**: Run the SQL script above

### "Invalid API key"
- **Cause**: Wrong Supabase credentials
- **Fix**: Check your .env.local file

### "Phone number already exists"  
- **Cause**: User already registered
- **Fix**: Say "I already have an account"

## Next Steps

After fixing the database:

1. Start WhatsApp bridge: `cd ../whatsapp-mcp/whatsapp-bridge && go run main.go`
2. Start backend: `python main.py`
3. Test registration flow with WhatsApp
4. Test fund addition and challenge creation

The system is now much more robust and handles edge cases properly! 🚀 