create table if not exists public.x_publications (
  id uuid primary key default gen_random_uuid(),
  source_key text not null unique,
  source_run_id bigint,
  title text not null,
  article_url text not null,
  status text not null default 'pending' check (status in ('pending', 'published', 'failed')),
  x_post_id text,
  x_post_url text,
  error_message text,
  attempts integer not null default 0,
  last_attempt_at timestamptz,
  published_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists x_publications_status_idx on public.x_publications(status);
create index if not exists x_publications_source_run_idx on public.x_publications(source_run_id);

alter table public.x_publications enable row level security;
