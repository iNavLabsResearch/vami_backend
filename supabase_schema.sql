-- Core RBAC tables for Vami Surat pump management

create type user_role as enum ('software_owner', 'pump_owner', 'branch_manager');

create table if not exists organisations (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  address text,
  city text,
  state text,
  country text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  full_name text,
  role user_role not null,
  organisation_id uuid references organisations(id) on delete set null,
  password_hash text not null,
  is_active boolean not null default true,
  failed_login_attempts int not null default 0,
  lock_until timestamptz,
  last_login_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_users_email on users (email);
create index if not exists idx_users_role on users (role);

create table if not exists pumps (
  id uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations(id) on delete cascade,
  name text not null,
  location text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_pumps_organisation_id on pumps (organisation_id);

create table if not exists shifts (
  id uuid primary key default gen_random_uuid(),
  pump_id uuid not null references pumps(id) on delete cascade,
  manager_id uuid references users(id) on delete set null,
  staff_name text,
  start_time timestamptz not null,
  end_time timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_shifts_pump_id on shifts (pump_id);
create index if not exists idx_shifts_manager_id on shifts (manager_id);
create index if not exists idx_shifts_start_time on shifts (start_time);

