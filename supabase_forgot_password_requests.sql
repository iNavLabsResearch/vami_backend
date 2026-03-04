-- Run this in Supabase SQL editor to create the forgot_password_requests table for the login "Forgot password?" flow.
-- Admin notifications list these requests; pump owner is notified when the request belongs to a branch_manager in their org.

CREATE TABLE IF NOT EXISTS forgot_password_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email_or_phone TEXT NOT NULL,
  user_id UUID,
  user_role TEXT,
  organisation_id UUID,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at TIMESTAMPTZ
);

-- Optional: RLS policies (adjust to your auth pattern)
-- ALTER TABLE forgot_password_requests ENABLE ROW LEVEL SECURITY;
