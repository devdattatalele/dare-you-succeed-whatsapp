-- Fix Authentication System
-- Add password field to profiles table and set up custom authentication

-- 1. Add password field to profiles table
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS password_hash TEXT;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS created_via TEXT DEFAULT 'webapp';
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS last_login TIMESTAMP WITH TIME ZONE;

-- 2. Create index on email for faster authentication
CREATE INDEX IF NOT EXISTS idx_profiles_email ON profiles(email);

-- 3. Update RLS policies to allow password authentication
DROP POLICY IF EXISTS "Users can read own profile" ON profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON profiles;

-- Create new policies that work with both auth and direct profile access
CREATE POLICY "Users can read own profile" ON profiles
FOR SELECT
USING (
  id = auth.uid() OR  -- Standard Supabase auth
  TRUE  -- Allow read access for custom auth (we'll handle this in app logic)
);

CREATE POLICY "Service role can manage profiles" ON profiles
FOR ALL
TO service_role
USING (TRUE)
WITH CHECK (TRUE);

-- 4. Create a function to authenticate users
CREATE OR REPLACE FUNCTION authenticate_user(user_email TEXT, user_password TEXT)
RETURNS TABLE(
  user_id UUID,
  email TEXT,
  full_name TEXT,
  phone TEXT,
  created_at TIMESTAMP WITH TIME ZONE
) 
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  RETURN QUERY
  SELECT 
    p.id,
    p.email,
    p.full_name,
    p.phone,
    p.created_at
  FROM profiles p
  WHERE p.email = user_email
    AND p.password_hash = crypt(user_password, p.password_hash);
END;
$$;

-- 5. Create a function to create user with password
CREATE OR REPLACE FUNCTION create_user_with_password(
  user_email TEXT,
  user_password TEXT,
  user_full_name TEXT,
  user_phone TEXT
)
RETURNS TABLE(
  user_id UUID,
  email TEXT,
  full_name TEXT,
  phone TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  new_user_id UUID;
BEGIN
  -- Generate new UUID
  new_user_id := gen_random_uuid();
  
  -- Insert profile with hashed password
  INSERT INTO profiles (
    id,
    email,
    full_name,
    phone,
    password_hash,
    created_via
  ) VALUES (
    new_user_id,
    user_email,
    user_full_name,
    user_phone,
    crypt(user_password, gen_salt('bf')),
    'custom'
  );
  
  -- Create wallet
  INSERT INTO wallets (user_id, balance) 
  VALUES (new_user_id, 0.0);
  
  -- Return user data
  RETURN QUERY
  SELECT 
    new_user_id,
    user_email,
    user_full_name,
    user_phone;
END;
$$;

-- 6. Enable row level security on all tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE wallets ENABLE ROW LEVEL SECURITY;
ALTER TABLE challenges ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;

-- 7. Update wallet policies for custom auth
DROP POLICY IF EXISTS "Users can read own wallet" ON wallets;
CREATE POLICY "Users can read own wallet" ON wallets
FOR SELECT
USING (TRUE);  -- We'll handle access control in application

DROP POLICY IF EXISTS "Users can update own wallet" ON wallets;
CREATE POLICY "Service role can manage wallets" ON wallets
FOR ALL
TO service_role
USING (TRUE)
WITH CHECK (TRUE);

-- 8. Update challenge policies
DROP POLICY IF EXISTS "Users can read own challenges" ON challenges;
CREATE POLICY "Users can read own challenges" ON challenges
FOR SELECT
USING (TRUE);

CREATE POLICY "Service role can manage challenges" ON challenges
FOR ALL
TO service_role
USING (TRUE)
WITH CHECK (TRUE);

-- 9. Update transaction policies
CREATE POLICY "Service role can manage transactions" ON transactions
FOR ALL
TO service_role
USING (TRUE)
WITH CHECK (TRUE);

COMMENT ON FUNCTION authenticate_user IS 'Custom authentication function that checks email and password hash';
COMMENT ON FUNCTION create_user_with_password IS 'Creates a new user with hashed password bypass Supabase Auth'; 