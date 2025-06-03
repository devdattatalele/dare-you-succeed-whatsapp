-- Quick Fix: Add phone column to profiles table if missing
-- Run this FIRST if you get column errors

-- Add phone column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'profiles' AND column_name = 'phone') THEN
        ALTER TABLE profiles ADD COLUMN phone TEXT;
        RAISE NOTICE '✅ Added phone column to profiles table';
    ELSE
        RAISE NOTICE '✅ Phone column already exists in profiles table';
    END IF;
END $$;

-- Create index for phone lookups
CREATE INDEX IF NOT EXISTS idx_profiles_phone ON profiles(phone);

RAISE NOTICE '🔧 Quick fix complete - now run fix_auth_integration.sql'; 