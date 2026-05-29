-- RevvUp — Supabase schema setup
-- Run this in Supabase Dashboard -> SQL Editor.

-- 1. Profiles table ----------------------------------------------------------
-- One row per auth user. Tracks role + approval status.
--   role:   'client' | 'showroom_owner' | 'admin'
--   status: 'active' | 'pending' | 'rejected'
-- Showroom owners start as 'pending' until the developer approves them.
create table if not exists public.profiles (
    id                 uuid primary key references auth.users(id) on delete cascade,
    email              text        not null,
    full_name          text,
    role               text        not null default 'client'
                          check (role in ('client', 'showroom_owner', 'admin')),
    status             text        not null default 'active'
                          check (status in ('active', 'pending', 'rejected')),
    showroom_name      text,
    showroom_address   text,
    phone              text,
    confirmation_token uuid,
    created_at         timestamptz not null default now()
);

alter table public.profiles enable row level security;

drop policy if exists "Users read own profile" on public.profiles;
create policy "Users read own profile"
    on public.profiles for select
    using (auth.uid() = id);

-- 2. Bikes table -------------------------------------------------------------
create table if not exists public.bikes (
    id            uuid primary key default gen_random_uuid(),
    owner_id      uuid references public.profiles(id) on delete set null,
    name          text        not null,
    brand         text        not null,
    price         numeric     not null,
    image_url     text,
    top_speed_mph integer,
    weight_lbs    integer,
    engine_cc     integer,
    horsepower    integer,
    year          integer,
    created_at    timestamptz not null default now()
);

-- If the bikes table already existed, make sure owner_id is present:
alter table public.bikes add column if not exists owner_id uuid references public.profiles(id) on delete set null;

-- 3. Row Level Security ------------------------------------------------------
-- The backend uses the service role key, which bypasses RLS. This policy lets
-- the public/anon key read the catalog directly if you ever need it.
alter table public.bikes enable row level security;

drop policy if exists "Public read bikes" on public.bikes;
create policy "Public read bikes"
    on public.bikes for select
    using (true);

-- 4. Seed data (optional) ----------------------------------------------------
insert into public.bikes (name, brand, price, image_url, top_speed_mph, weight_lbs, engine_cc, horsepower, year)
values
    ('Panigale V4 S', 'Ducati', 28995, 'https://images.unsplash.com/photo-1558981403-c5f9899a28bc?w=800', 186, 430, 1103, 214, 2024),
    ('S 1000 RR', 'BMW', 19995, 'https://images.unsplash.com/photo-1568772585407-9361f9bf3a87?w=800', 186, 437, 999, 205, 2024),
    ('CBR1000RR-R FIREBLADE SP', 'Honda', 28500, 'https://images.unsplash.com/photo-1609630875171-a86a521a48fe?w=800', 180, 443, 999, 214, 2024)
on conflict do nothing;

-- 5. Storage bucket for images ----------------------------------------------
-- Create a PUBLIC bucket named 'bike-images':
--   Dashboard -> Storage -> New bucket -> name: bike-images, Public: ON
-- Or run:
insert into storage.buckets (id, name, public)
values ('bike-images', 'bike-images', true)
on conflict (id) do nothing;

-- 6. (Optional) Promote yourself to admin -----------------------------------
-- update public.profiles set role = 'admin', status = 'active'
-- where email = 'you@example.com';
