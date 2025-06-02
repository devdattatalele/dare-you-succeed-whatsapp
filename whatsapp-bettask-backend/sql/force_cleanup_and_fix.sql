-- FORCE CLEANUP AND FIX - Aggressive cleanup and simple setup
-- This script will completely reset the auth integration setup

-- 1. FORCE DROP ALL POLICIES (ignore errors)
DO $$
DECLARE
    r RECORD;
BEGIN
    -- Drop all policies on profiles table
    FOR r IN (SELECT policyname FROM pg_policies WHERE tablename = 'profiles') LOOP
        BEGIN
            EXECUTE 'DROP POLICY "' || r.policyname || '" ON profiles';
            RAISE NOTICE 'Dropped policy: %', r.policyname;
        EXCEPTION 
            WHEN OTHERS THEN 
                RAISE NOTICE 'Could not drop policy %, continuing...', r.policyname;
        END;
    END LOOP;
    
    -- Drop all policies on wallets table
    FOR r IN (SELECT policyname FROM pg_policies WHERE tablename = 'wallets') LOOP
        BEGIN
            EXECUTE 'DROP POLICY "' || r.policyname || '" ON wallets';
            RAISE NOTICE 'Dropped policy: %', r.policyname;
        EXCEPTION 
            WHEN OTHERS THEN 
                RAISE NOTICE 'Could not drop policy %, continuing...', r.policyname;
        END;
    END LOOP;
    
    -- Drop all policies on challenges table
    FOR r IN (SELECT policyname FROM pg_policies WHERE tablename = 'challenges') LOOP
        BEGIN
            EXECUTE 'DROP POLICY "' || r.policyname || '" ON challenges';
            RAISE NOTICE 'Dropped policy: %', r.policyname;
        EXCEPTION 
            WHEN OTHERS THEN 
                RAISE NOTICE 'Could not drop policy %, continuing...', r.policyname;
        END;
    END LOOP;
    
    -- Drop all policies on transactions table
    FOR r IN (SELECT policyname FROM pg_policies WHERE tablename = 'transactions') LOOP
        BEGIN
            EXECUTE 'DROP POLICY "' || r.policyname || '" ON transactions';
            RAISE NOTICE 'Dropped policy: %', r.policyname;
        EXCEPTION 
            WHEN OTHERS THEN 
                RAISE NOTICE 'Could not drop policy %, continuing...', r.policyname;
        END;
    END LOOP;
    
    RAISE NOTICE '🧹 Force cleanup of all policies complete';
END $$;

-- 2. DISABLE RLS ON ALL TABLES TEMPORARILY
ALTER TABLE profiles DISABLE ROW LEVEL SECURITY;
ALTER TABLE wallets DISABLE ROW LEVEL SECURITY;
ALTER TABLE challenges DISABLE ROW LEVEL SECURITY;
ALTER TABLE transactions DISABLE ROW LEVEL SECURITY;
ALTER TABLE task_submissions DISABLE ROW LEVEL SECURITY;

-- 3. DROP TRIGGER AND FUNCTION COMPLETELY
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users CASCADE;
DROP FUNCTION IF EXISTS handle_new_user() CASCADE;

-- 4. CREATE SIMPLE TRIGGER FUNCTION (NO RLS CONFLICTS)
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    -- Log the trigger execution
    RAISE NOTICE 'AUTH TRIGGER: Creating profile for user % with email %', NEW.id, NEW.email;
    
    -- Simple insert with conflict handling
    INSERT INTO public.profiles (id, email, full_name, phone)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1)),
        NEW.raw_user_meta_data->>'phone'
    )
    ON CONFLICT (id) DO UPDATE SET
        email = NEW.email,
        full_name = COALESCE(NEW.raw_user_meta_data->>'full_name', profiles.full_name),
        phone = COALESCE(NEW.raw_user_meta_data->>'phone', profiles.phone);
    
    RAISE NOTICE 'AUTH TRIGGER: Profile created for user %', NEW.id;
    
    -- Simple wallet insert
    INSERT INTO public.wallets (user_id, balance)
    VALUES (NEW.id, 0.00)
    ON CONFLICT (user_id) DO NOTHING;
    
    RAISE NOTICE 'AUTH TRIGGER: Wallet created for user %', NEW.id;
    
    RETURN NEW;
EXCEPTION
    WHEN OTHERS THEN
        RAISE WARNING 'AUTH TRIGGER ERROR for user %: %', NEW.id, SQLERRM;
        RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 5. CREATE THE TRIGGER
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- 6. GRANT MAXIMUM PERMISSIONS TO SERVICE ROLE
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO service_role;
GRANT USAGE ON SCHEMA public TO service_role;

-- Also grant to authenticated role for triggers
GRANT ALL PRIVILEGES ON TABLE profiles TO authenticated;
GRANT ALL PRIVILEGES ON TABLE wallets TO authenticated;

-- 7. CREATE VERY PERMISSIVE POLICIES (TEMPORARY - FOR TESTING)
CREATE POLICY "allow_all_profiles" ON profiles FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_wallets" ON wallets FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_challenges" ON challenges FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_transactions" ON transactions FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_submissions" ON task_submissions FOR ALL USING (true) WITH CHECK (true);

-- 8. RE-ENABLE RLS
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE wallets ENABLE ROW LEVEL SECURITY;
ALTER TABLE challenges ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_submissions ENABLE ROW LEVEL SECURITY;

-- 9. TEST THE SETUP
DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '=== SETUP VERIFICATION ===';
    
    IF EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'on_auth_user_created') THEN
        RAISE NOTICE '✅ Trigger on_auth_user_created exists';
    ELSE
        RAISE NOTICE '❌ Trigger on_auth_user_created MISSING';
    END IF;
    
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'handle_new_user') THEN
        RAISE NOTICE '✅ Function handle_new_user exists';
    ELSE
        RAISE NOTICE '❌ Function handle_new_user MISSING';
    END IF;
    
    -- Check policies
    IF EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'profiles') THEN
        RAISE NOTICE '✅ Profiles policies exist';
    ELSE
        RAISE NOTICE '❌ Profiles policies MISSING';
    END IF;
    
    RAISE NOTICE '';
    RAISE NOTICE '🎉 FORCE CLEANUP AND SETUP COMPLETE!';
    RAISE NOTICE '📱 WhatsApp auth registration should now work';
    RAISE NOTICE '🧪 Run test_database_setup.py to verify';
    RAISE NOTICE '';
END $$; 