-- E-Book Factory — remote panel schema (Postgres, e.g. Vercel Postgres / Neon)
--
-- This database is a MIRROR + OUTBOX, not the source of truth. The real pipeline
-- (state machine, QC, validators, locks) lives in the local Python factory engine.
-- This DB only lets the Vercel-hosted panel show live state and queue actions for
-- the local engine to apply.
--
-- Run once against a fresh database: psql $DATABASE_URL -f schema.sql

create table if not exists kv_state (
  id text primary key,              -- always 'singleton'
  data jsonb not null,
  updated_at timestamptz not null default now()
);

create table if not exists book_details (
  book_id text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);

create table if not exists users (
  partner text primary key,
  salt text not null,
  pin_hash text not null,
  created_at timestamptz not null default now()
);

create table if not exists sessions (
  token text primary key,
  partner text not null,
  expires_at timestamptz not null
);

create table if not exists pending_actions (
  id text primary key,
  partner text not null,
  payload jsonb not null,
  status text not null default 'pending',   -- pending | done | error
  result jsonb,
  error text,
  created_at timestamptz not null default now(),
  processed_at timestamptz
);

create index if not exists pending_actions_status_idx on pending_actions (status, created_at);
create index if not exists sessions_expires_idx on sessions (expires_at);
