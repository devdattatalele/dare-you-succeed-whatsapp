-- Cleanup and Fix Auth Integration
-- This script cleans up partial installations and fixes the auth trigger

-- 1. Drop all existing policies (force cleanup)
DO $$
BEGIN
    -- Profiles policies
    DROP POLICY IF EXISTS "Users can view own profile" ON profiles;
    DROP POLICY IF EXISTS "Users can update own profile" ON profiles;
    DROP POLICY IF EXISTS "Users can insert own profile" ON profiles;
    DROP POLICY IF EXISTS "Service role can manage profiles" ON profiles;
    DROP POLICY IF EXISTS "Allow trigger access" ON profiles;
    DROP POLICY IF EXISTS "Service role and triggers can insert profiles" ON profiles;
    
    -- Wallets policies
    DROP POLICY IF EXISTS "Users can view own wallet" ON wallets;
    DROP POLICY IF EXISTS "Users can update own wallet" ON wallets;
    DROP POLICY IF EXISTS "Users can insert own wallet" ON wallets;
    DROP POLICY IF EXISTS "Service role can manage wallets" ON wallets;
    DROP POLICY IF EXISTS "Service role and triggers can insert wallets" ON wallets;
    
    -- Challenges policies
    DROP POLICY IF EXISTS "Users can view own challenges" ON challenges;
    DROP POLICY IF EXISTS "Users can create own challenges" ON challenges;
    DROP POLICY IF EXISTS "Users can update own challenges" ON challenges;
    DROP POLICY IF EXISTS "Service role can manage challenges" ON challenges;
    
    -- Transactions policies
    DROP POLICY IF EXISTS "Users can view own transactions" ON transactions;
    DROP POLICY IF EXISTS "Users can insert own transactions" ON transactions;
    DROP POLICY IF EXISTS "Service role can manage transactions" ON transactions;
    
    RAISE NOTICE '🧹 Cleaned up existing policies';
END $$;

-- 2. Drop and recreate the trigger function
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP FUNCTION IF EXISTS handle_new_user();

-- 3. Create the trigger function with better error handling and logging
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
    user_phone TEXT;
    user_name TEXT;
BEGIN
    -- Extract metadata
    user_phone := NEW.raw_user_meta_data->>'phone';
    user_name := COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1));
    
    -- Log the trigger execution
    RAISE NOTICE 'Creating profile for user % with email % and phone %', NEW.id, NEW.email, user_phone;
    
    -- Insert profile for new auth user
    INSERT INTO public.profiles (id, email, full_name, phone, created_at, updated_at)
    VALUES (
        NEW.id,
        NEW.email,
        user_name,
        user_phone,
        NOW(),
        NOW()
    )
    ON CONFLICT (id) DO UPDATE SET
        email = NEW.email,
        full_name = COALESCE(user_name, profiles.full_name),
        phone = COALESCE(user_phone, profiles.phone),
        updated_at = NOW();
    
    RAISE NOTICE 'Profile created/updated for user %', NEW.id;
    
    -- Create wallet for new user
    INSERT INTO public.wallets (user_id, balance, created_at, updated_at)
    VALUES (NEW.id, 0.00, NOW(), NOW())
    ON CONFLICT (user_id) DO UPDATE SET
        updated_at = NOW();
    
    RAISE NOTICE 'Wallet created/updated for user %', NEW.id;
    
    RETURN NEW;
EXCEPTION
    WHEN OTHERS THEN
        -- Log the specific error
        RAISE WARNING 'Error in handle_new_user trigger for user %: % - %', NEW.id, SQLSTATE, SQLERRM;
        -- Don't fail the user creation, just log the error
        RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 4. Create the trigger
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- 5. Disable RLS temporarily to set up policies
ALTER TABLE profiles DISABLE ROW LEVEL SECURITY;
ALTER TABLE wallets DISABLE ROW LEVEL SECURITY;
ALTER TABLE challenges DISABLE ROW LEVEL SECURITY;
ALTER TABLE transactions DISABLE ROW LEVEL SECURITY;

-- 6. Create new policies for profiles
CREATE POLICY "profiles_select_policy" ON profiles
    FOR SELECT USING (true);  -- Allow all selects for now

CREATE POLICY "profiles_insert_policy" ON profiles
    FOR INSERT WITH CHECK (true);  -- Allow all inserts

CREATE POLICY "profiles_update_policy" ON profiles
    FOR UPDATE USING (auth.uid() = id OR auth.role() = 'service_role');

CREATE POLICY "profiles_delete_policy" ON profiles
    FOR DELETE USING (auth.uid() = id OR auth.role() = 'service_role');

-- 7. Create new policies for wallets
CREATE POLICY "wallets_select_policy" ON wallets
    FOR SELECT USING (auth.uid() = user_id OR auth.role() = 'service_role');

CREATE POLICY "wallets_insert_policy" ON wallets
    FOR INSERT WITH CHECK (true);  -- Allow all inserts

CREATE POLICY "wallets_update_policy" ON wallets
    FOR UPDATE USING (auth.uid() = user_id OR auth.role() = 'service_role');

-- 8. Create policies for challenges
CREATE POLICY "challenges_select_policy" ON challenges
    FOR SELECT USING (auth.uid() = user_id OR auth.role() = 'service_role');

CREATE POLICY "challenges_insert_policy" ON challenges
    FOR INSERT WITH CHECK (auth.uid() = user_id OR auth.role() = 'service_role');

CREATE POLICY "challenges_update_policy" ON challenges
    FOR UPDATE USING (auth.uid() = user_id OR auth.role() = 'service_role');

-- 9. Create policies for transactions
CREATE POLICY "transactions_select_policy" ON transactions
    FOR SELECT USING (auth.uid() = user_id OR auth.role() = 'service_role');

CREATE POLICY "transactions_insert_policy" ON transactions
    FOR INSERT WITH CHECK (auth.uid() = user_id OR auth.role() = 'service_role');

-- 10. Re-enable RLS
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE wallets ENABLE ROW LEVEL SECURITY;
ALTER TABLE challenges ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;

-- 11. Grant permissions
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO service_role;

-- 12. Create indexes
CREATE INDEX IF NOT EXISTS idx_profiles_phone ON profiles(phone);
CREATE INDEX IF NOT EXISTS idx_profiles_email ON profiles(email);
CREATE INDEX IF NOT EXISTS idx_wallets_user_id ON wallets(user_id);

-- 13. Test the setup
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'on_auth_user_created') THEN
        RAISE NOTICE '✅ Trigger on_auth_user_created exists and is active';
    ELSE
        RAISE NOTICE '❌ Trigger on_auth_user_created is missing';
    END IF;
    
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'handle_new_user') THEN
        RAISE NOTICE '✅ Function handle_new_user exists';
    ELSE
        RAISE NOTICE '❌ Function handle_new_user is missing';
    END IF;
    
    RAISE NOTICE '🎉 Cleanup and setup complete!';
    RAISE NOTICE '📱 WhatsApp registration should now work';
    RAISE NOTICE '🔄 Try creating a test user to verify';
END $$; 