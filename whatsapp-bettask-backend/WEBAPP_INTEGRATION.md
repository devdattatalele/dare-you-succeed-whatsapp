# WhatsApp Backend & Webapp Integration

This document explains how the WhatsApp backend has been integrated with the webapp to provide seamless user experience across both platforms.

## 🎯 Integration Goals

✅ **Unified Authentication**: Users can create accounts via WhatsApp and login to webapp with same credentials  
✅ **Shared Challenges**: Challenges created on WhatsApp appear in webapp and vice versa  
✅ **Synchronized Wallets**: Balance and transactions are consistent across platforms  
✅ **Cross-Platform Compatibility**: Same user experience regardless of entry point  

## 🔧 Database Setup

### 1. Run the Integration SQL Script

Execute the following script in your Supabase SQL editor:

```bash
# Run the auth integration setup
psql -h your-supabase-host -U postgres -d postgres -f sql/setup_auth_integration.sql
```

Or copy the contents of `sql/setup_auth_integration.sql` and run in Supabase dashboard.

### 2. Verify Database Schema

After running the script, your database should have:

- **Profiles Table**: Links to `auth.users` with phone numbers
- **Database Triggers**: Auto-create profiles when auth users register
- **RLS Policies**: Proper security for both platforms
- **Service Role Access**: WhatsApp backend can manage user data

## 🔐 Authentication Flow

### WhatsApp User Registration

1. **User sends message** → WhatsApp backend prompts for registration
2. **Email collection** → Validates and checks for duplicates
3. **Password creation** → Enforces security requirements
4. **Name collection** → For profile display
5. **Account creation** → Uses `supabase.auth.signUp()` (same as webapp)
6. **Profile & wallet creation** → Automatic via database triggers

### Webapp User Registration

1. **User visits webapp** → Fills registration form
2. **Account creation** → Uses `supabase.auth.signUp()`
3. **Profile & wallet creation** → Automatic via database triggers
4. **Login success** → Access to dashboard

### Cross-Platform Login

- **WhatsApp**: Automatic login via phone number lookup
- **Webapp**: Email/password login via Supabase Auth
- **Shared data**: Both platforms access same user profile and challenges

## 📊 Data Synchronization

### Challenge Creation

**WhatsApp Backend:**
```python
# Creates challenge with proper auth user ID
challenge_data = {
    "user_id": auth_user.id,  # From Supabase Auth
    "title": "My goal",
    "amount": 100,
    # ... other fields
}
```

**Webapp:**
```typescript
// Uses same auth user ID
const { data: { user } } = await supabase.auth.getUser();
const challenge = {
    user_id: user.id,  // Same ID as WhatsApp
    title: "My goal",
    amount: 100,
    // ... other fields
}
```

### Wallet Management

Both platforms use the same `wallets` table:
- **Balance updates** sync automatically
- **Transaction history** shared across platforms
- **Payment processing** consistent logic

## 🔀 Message Routing

### WhatsApp Backend Flow

```python
async def route_message(user_id, phone_number, message):
    # 1. Check if user is registered (auth-based)
    user_profile = await supabase_client.get_user_by_phone(phone_number)
    
    if not user_profile:
        # 2. Prompt for registration via Supabase Auth
        return await registration_handler.handle_registration_flow(...)
    
    # 3. Route message to appropriate handler
    return await intent_router.route_message(...)
```

### User Profile Lookup

```python
async def get_user_by_phone(phone_number):
    # Queries profiles table linked to auth.users
    result = self.client.table("profiles").select("*").eq("phone", phone_number).execute()
    return result.data[0] if result.data else None
```

## 🚀 Quick Start Integration

### 1. Update Your Supabase Database

```sql
-- Run this in Supabase SQL editor
\i sql/setup_auth_integration.sql
```

### 2. Start WhatsApp Backend

```bash
cd whatsapp-bettask-backend
python main.py
```

### 3. Test Integration

1. **Create user via WhatsApp**:
   - Send "register" to your WhatsApp bot
   - Follow registration flow with email/password
   - Create a challenge via WhatsApp

2. **Login to webapp**:
   - Visit your webapp URL
   - Login with same email/password
   - Verify challenge appears in dashboard

3. **Create challenge via webapp**:
   - Create challenge in webapp
   - Check WhatsApp for challenge confirmation

## 🔍 Troubleshooting

### Common Issues

**❌ "User not found" errors**
```bash
# Check if profiles table is properly linked
SELECT p.*, u.email FROM profiles p 
LEFT JOIN auth.users u ON p.id = u.id;
```

**❌ RLS Policy errors**
```bash
# Verify service role has access
SELECT * FROM pg_policies WHERE tablename = 'profiles';
```

**❌ Challenge sync issues**
```bash
# Check if challenges use auth user IDs
SELECT user_id, title FROM challenges 
WHERE user_id IN (SELECT id FROM auth.users);
```

### Debug Commands

```python
# Test user creation
python -c "
import asyncio
from services.supabase_client import SupabaseClient
client = SupabaseClient()
print(asyncio.run(client.create_auth_user(
    'test@example.com', 'password123', 'Test User', '1234567890'
)))
"

# Test phone lookup
python -c "
import asyncio
from services.supabase_client import SupabaseClient
client = SupabaseClient()
print(asyncio.run(client.get_user_by_phone('1234567890')))
"
```

## 📁 File Structure

```
whatsapp-bettask-backend/
├── services/
│   └── supabase_client.py          # Enhanced with auth integration
├── handlers/
│   └── registration_handler.py     # Updated for Supabase Auth
├── sql/
│   └── setup_auth_integration.sql  # Database setup script
├── main.py                         # Updated message processing
└── WEBAPP_INTEGRATION.md          # This file

src/ (webapp)
├── integrations/supabase/
│   ├── client.ts                   # Same Supabase connection
│   └── types.ts                    # Shared database types
├── hooks/
│   ├── useChallenges.ts           # Uses auth.uid()
│   └── useWallet.ts               # Uses auth.uid()
└── components/
    └── Auth.tsx                    # Supabase Auth signup/login
```

## ✅ Verification Checklist

- [ ] Database triggers create profiles for new auth users
- [ ] WhatsApp registration creates Supabase Auth users
- [ ] Both platforms use same user IDs for challenges
- [ ] Wallet balances sync between platforms
- [ ] RLS policies allow service role access
- [ ] Phone number lookup works correctly
- [ ] Cross-platform challenge creation works
- [ ] Transaction history is shared

## 🎉 Success!

Once integration is complete, users can:

1. **Register via WhatsApp** → Login to webapp with same credentials
2. **Create challenges anywhere** → See them everywhere
3. **Manage funds seamlessly** → Consistent balance across platforms
4. **Switch between platforms** → No data loss or confusion

The system now provides a truly unified experience! 🚀 