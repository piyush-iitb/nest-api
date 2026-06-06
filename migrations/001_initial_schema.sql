-- ============================================================
-- Migration 001: Initial schema
-- Creates the core tables we need to get started:
--   users         — buyer accounts (phone-OTP auth)
--   listings      — properties
--   listing_media — photos/illustrations linked to a listing
--   shortlists    — many-to-many: which users saved which listings
--   intents       — user buying intent history (audit trail)
--   events        — behavioral signals (listing views, etc.)
--   leads         — when a user requests callback or visit
-- ============================================================

-- Helper: auto-update updated_at on row changes
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- ============================================================
-- users
-- Phone is the primary identifier. No email/password.
-- ============================================================
CREATE TABLE users (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  phone           VARCHAR(20) NOT NULL UNIQUE,
  name            VARCHAR(120),
  current_intent  VARCHAR(20) CHECK (current_intent IN ('casual', 'soon', 'serious')),
  city            VARCHAR(60),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER users_set_updated_at
  BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE INDEX idx_users_phone ON users(phone);


-- ============================================================
-- listings
-- Properties uploaded by the supply partner.
-- ============================================================
CREATE TABLE listings (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title           VARCHAR(200) NOT NULL,
  subtitle        VARCHAR(200),
  description     TEXT,
  locality        VARCHAR(120) NOT NULL,
  city            VARCHAR(60) NOT NULL,
  lat             NUMERIC(9, 6),
  lng             NUMERIC(9, 6),
  price           BIGINT NOT NULL CHECK (price >= 0),    -- stored in rupees
  bhk             SMALLINT NOT NULL CHECK (bhk > 0),
  baths           SMALLINT NOT NULL CHECK (baths >= 0),
  area_sqft       INTEGER NOT NULL CHECK (area_sqft > 0),
  property_type   VARCHAR(40) NOT NULL,                  -- Apartment, Villa, Plot
  possession      VARCHAR(80),                           -- "Ready to move" or a date string
  builder         VARCHAR(120),
  age_years       VARCHAR(40),                           -- "3 years" or "Under construction"
  amenities       TEXT[] NOT NULL DEFAULT '{}',          -- array of amenity names
  illustration    VARCHAR(40),                           -- key into our SVG illustrations
  color           VARCHAR(10),                           -- hex color
  verified        BOOLEAN NOT NULL DEFAULT FALSE,
  verified_at     TIMESTAMPTZ,
  featured        BOOLEAN NOT NULL DEFAULT FALSE,
  status          VARCHAR(20) NOT NULL DEFAULT 'active'  -- active, sold, withdrawn
                  CHECK (status IN ('active', 'sold', 'withdrawn')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER listings_set_updated_at
  BEFORE UPDATE ON listings
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE INDEX idx_listings_city_locality ON listings(city, locality);
CREATE INDEX idx_listings_status ON listings(status) WHERE status = 'active';
CREATE INDEX idx_listings_featured ON listings(featured) WHERE featured = TRUE;
CREATE INDEX idx_listings_price ON listings(price);


-- ============================================================
-- shortlists
-- Each row = one user saved one listing.
-- ============================================================
CREATE TABLE shortlists (
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  listing_id  UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, listing_id)
);

CREATE INDEX idx_shortlists_user ON shortlists(user_id);


-- ============================================================
-- intents
-- Audit log of intent changes. The user's current intent is on the user row,
-- but every change is also recorded here so we can analyze intent journeys.
-- ============================================================
CREATE TABLE intents (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  intent      VARCHAR(20) NOT NULL CHECK (intent IN ('casual', 'soon', 'serious')),
  set_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_intents_user ON intents(user_id, set_at DESC);


-- ============================================================
-- events
-- Behavioral signals from the frontend (listing views, searches, etc.).
-- This is the raw stream we feed lead scoring later.
-- ============================================================
CREATE TABLE events (
  id          BIGSERIAL PRIMARY KEY,
  user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
  event_type  VARCHAR(40) NOT NULL,    -- listing_view, search, shortlist_add, compare_add, etc.
  payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_events_user_time ON events(user_id, created_at DESC);
CREATE INDEX idx_events_type_time ON events(event_type, created_at DESC);


-- ============================================================
-- leads
-- When a serious buyer requests a callback or schedules a visit.
-- ============================================================
CREATE TABLE leads (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  listing_id    UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  mode          VARCHAR(20) NOT NULL CHECK (mode IN ('callback', 'visit')),
  message       TEXT,
  visit_date    DATE,
  visit_time    VARCHAR(20),                            -- "10:00 AM" etc.
  intent_at_submission VARCHAR(20) NOT NULL,            -- snapshot for audit
  status        VARCHAR(20) NOT NULL DEFAULT 'new'      -- new, assigned, contacted, closed
                CHECK (status IN ('new', 'assigned', 'contacted', 'closed')),
  assigned_dealer_id UUID,                              -- foreign key to dealers table when we add it
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER leads_set_updated_at
  BEFORE UPDATE ON leads
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE INDEX idx_leads_user ON leads(user_id, created_at DESC);
CREATE INDEX idx_leads_listing ON leads(listing_id);
CREATE INDEX idx_leads_status ON leads(status);