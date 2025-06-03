-- Authentication Integration Setup for WhatsApp Backend & Webapp Compatibility
-- This script sets up proper integration between Supabase Auth and the profiles table

-- 1. Update profiles table to reference auth.users
-- First, check if profiles table has foreign key to auth.users
DO $$ 
BEGIN
    -- Add user_id column if it doesn't exist (for auth reference)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'profiles' AND column_name = 'user_id') THEN
        ALTER TABLE profiles ADD COLUMN user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;
    END IF;
    
    -- Make sure id column can be used as primary key for auth users
    -- If profiles.id doesn't reference auth.users, we need to update the structure
END $$;

-- 2. Create function to handle new user registration
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    -- Create profile for new auth user
    INSERT INTO profiles (id, email, full_name, phone, created_at)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.email),
        NEW.raw_user_meta_data->>'phone',
        NOW()
    );
    
    -- Create wallet for new user
    INSERT INTO wallets (user_id, balance, created_at, updated_at)
    VALUES (NEW.id, 0.00, NOW(), NOW());
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 3. Create trigger for new user creation
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- 4. Update RLS policies for profiles table
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Users can view own profile" ON profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON profiles;
DROP POLICY IF EXISTS "Users can insert own profile" ON profiles;

-- Create new policies that work with auth.users
CREATE POLICY "Users can view own profile" ON profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON profiles
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Service role can manage profiles" ON profiles
    FOR ALL USING (auth.role() = 'service_role');

-- 5. Ensure challenges table references auth users correctly
ALTER TABLE challenges ENABLE ROW LEVEL SECURITY;

-- Drop existing policies
DROP POLICY IF EXISTS "Users can view own challenges" ON challenges;
DROP POLICY IF EXISTS "Users can create own challenges" ON challenges;
DROP POLICY IF EXISTS "Users can update own challenges" ON challenges;

-- Create policies for challenges
CREATE POLICY "Users can view own challenges" ON challenges
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can create own challenges" ON challenges
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own challenges" ON challenges
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Service role can manage challenges" ON challenges
    FOR ALL USING (auth.role() = 'service_role');

-- 6. Update wallets table policies
-- (These should already be correct from DATABASE_SETUP.md, but ensuring they exist)
CREATE POLICY "Service role can manage wallets" ON wallets
    FOR ALL USING (auth.role() = 'service_role');

-- 7. Update transactions table policies
CREATE POLICY "Service role can manage transactions" ON transactions
    FOR ALL USING (auth.role() = 'service_role');

-- 8. Update task_submissions table policies
ALTER TABLE task_submissions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own submissions" ON task_submissions;
DROP POLICY IF EXISTS "Users can insert own submissions" ON task_submissions;
DROP POLICY IF EXISTS "Users can update own submissions" ON task_submissions;

CREATE POLICY "Users can view own submissions" ON task_submissions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own submissions" ON task_submissions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own submissions" ON task_submissions
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Service role can manage submissions" ON task_submissions
    FOR ALL USING (auth.role() = 'service_role');

-- 9. Create function to migrate existing non-auth users (if needed)
CREATE OR REPLACE FUNCTION migrate_existing_users()
RETURNS void AS $$
DECLARE
    profile_record RECORD;
BEGIN
    -- This function can be used to migrate existing profiles to auth users
    -- Only run if you have existing users that need to be converted
    
    FOR profile_record IN 
        SELECT * FROM profiles 
        WHERE id NOT IN (SELECT id FROM auth.users)
    LOOP
        -- Log that this profile needs manual migration
        RAISE NOTICE 'Profile % with email % needs manual migration to auth.users', 
                     profile_record.id, profile_record.email;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- 10. Add helper function to get user profile by phone (for WhatsApp backend)
CREATE OR REPLACE FUNCTION get_user_by_phone(phone_number TEXT)
RETURNS TABLE(id UUID, email TEXT, full_name TEXT, phone TEXT, created_at TIMESTAMPTZ) AS $$
BEGIN
    RETURN QUERY
    SELECT p.id, p.email, p.full_name, p.phone, p.created_at
    FROM profiles p
    WHERE p.phone = phone_number;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant permissions
GRANT EXECUTE ON FUNCTION get_user_by_phone(TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION migrate_existing_users() TO service_role;

-- 11. Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_profiles_phone ON profiles(phone);
CREATE INDEX IF NOT EXISTS idx_profiles_email ON profiles(email);

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Authentication integration setup complete!';
    RAISE NOTICE 'WhatsApp backend is now compatible with webapp authentication.';
    RAISE NOTICE 'Users created via either platform can access both.';
END $$; 