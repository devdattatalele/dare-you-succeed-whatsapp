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

-- Add some helpful comments
COMMENT ON TABLE payment_requests IS 'Stores UPI payment requests for fund additions and registration';
COMMENT ON COLUMN payment_requests.metadata IS 'Stores additional info like email for registration, transaction details, etc.';
COMMENT ON COLUMN payment_requests.status IS 'Payment status: pending (awaiting payment), approved (payment verified), rejected (invalid payment), expired (timeout)';

-- Create a storage bucket for payment screenshots if it doesn't exist
INSERT INTO storage.buckets (id, name, public) 
VALUES ('payment-proofs', 'payment-proofs', false)
ON CONFLICT (id) DO NOTHING;

-- Set up RLS policies for payment-proofs bucket
CREATE POLICY IF NOT EXISTS "Anyone can upload payment proofs" ON storage.objects 
FOR INSERT WITH CHECK (bucket_id = 'payment-proofs');

CREATE POLICY IF NOT EXISTS "Anyone can view payment proofs" ON storage.objects 
FOR SELECT USING (bucket_id = 'payment-proofs'); 