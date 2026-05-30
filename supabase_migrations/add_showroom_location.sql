-- Run in Supabase SQL Editor: showroom map pin (latitude / longitude)
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS latitude double precision,
  ADD COLUMN IF NOT EXISTS longitude double precision;

COMMENT ON COLUMN public.profiles.latitude IS 'Showroom map pin (WGS84)';
COMMENT ON COLUMN public.profiles.longitude IS 'Showroom map pin (WGS84)';
