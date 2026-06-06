-- ============================================================
-- Migration 002: OTP storage
-- Stores pending OTP codes during phone verification.
-- Codes expire after 10 minutes.
-- ============================================================

CREATE TABLE otps (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  phone         VARCHAR(20) NOT NULL,
  code          VARCHAR(6) NOT NULL,
  expires_at    TIMESTAMPTZ NOT NULL,
  consumed_at   TIMESTAMPTZ,                 -- NULL until verified; then set to NOW()
  attempts      SMALLINT NOT NULL DEFAULT 0, -- track wrong guesses to prevent brute force
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Look up pending OTPs by phone, fast.
CREATE INDEX idx_otps_phone_unconsumed
  ON otps(phone, created_at DESC)
  WHERE consumed_at IS NULL;

-- For cleanup jobs later: find expired ones quickly.
CREATE INDEX idx_otps_expires ON otps(expires_at);