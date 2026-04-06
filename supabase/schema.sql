create table if not exists public.courses (
  user_id text not null,
  course_id text not null,
  course_title text not null,
  start_date date not null,
  end_date date not null,
  daily_study_minutes integer not null default 120,
  created_at timestamptz not null default now(),
  primary key (user_id, course_id)
);

create table if not exists public.topics (
  user_id text not null,
  course_id text not null,
  topic_id text not null,
  title text not null,
  description text,
  difficulty integer not null default 3,
  estimated_minutes integer not null default 60,
  created_at timestamptz not null default now(),
  foreign key (user_id, course_id) references public.courses(user_id, course_id) on delete cascade,
  primary key (user_id, course_id, topic_id)
);

create table if not exists public.topic_edges (
  user_id text not null,
  course_id text not null,
  source text not null,
  target text not null,
  edge_type text not null,
  weight double precision not null default 0,
  created_at timestamptz not null default now(),
  foreign key (user_id, course_id) references public.courses(user_id, course_id) on delete cascade,
  primary key (user_id, course_id, source, target, edge_type)
);

create table if not exists public.study_plan_items (
  user_id text not null,
  course_id text not null,
  date date not null,
  topic_id text not null,
  topic_title text not null,
  planned_minutes integer not null,
  status text not null default 'pending',
  rationale text not null default '',
  created_at timestamptz not null default now(),
  foreign key (user_id, course_id) references public.courses(user_id, course_id) on delete cascade,
  primary key (user_id, course_id, date, topic_id)
);

create table if not exists public.progress_events (
  id bigserial primary key,
  user_id text not null,
  course_id text not null,
  topic_id text not null,
  date date not null,
  minutes_spent integer not null default 0,
  completed boolean not null default false,
  created_at timestamptz not null default now(),
  foreign key (user_id, course_id) references public.courses(user_id, course_id) on delete cascade
);

create index if not exists idx_progress_lookup
  on public.progress_events (user_id, course_id, topic_id, date);

create index if not exists idx_course_lookup
  on public.courses (user_id, course_id);

create index if not exists idx_topics_lookup
  on public.topics (user_id, course_id, topic_id);

create index if not exists idx_topic_edges_lookup
  on public.topic_edges (user_id, course_id, edge_type);

create index if not exists idx_plan_lookup
  on public.study_plan_items (user_id, course_id, date);
