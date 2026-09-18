-- Smart Fridge & Nutrition Coach - initial Supabase schema
-- Apply with `supabase db push` or paste in the Supabase SQL Editor.

create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    nutrition_profile jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.fridge_items (
    id bigint generated always as identity primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    name text not null check (char_length(name) between 1 and 100),
    quantity_g numeric(10, 2) not null check (quantity_g > 0 and quantity_g <= 100000),
    created_at timestamptz not null default now()
);

create index if not exists fridge_items_user_id_idx on public.fridge_items (user_id, id);

create table if not exists public.planned_meals (
    id bigint generated always as identity primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    day date not null,
    name text not null check (char_length(name) between 1 and 150),
    calories numeric(10, 2) not null check (calories >= 0 and calories <= 10000),
    protein numeric(10, 2) not null check (protein >= 0 and protein <= 1000),
    carbs numeric(10, 2) not null check (carbs >= 0 and carbs <= 2000),
    fat numeric(10, 2) not null check (fat >= 0 and fat <= 1000),
    created_at timestamptz not null default now()
);

create index if not exists planned_meals_user_day_idx on public.planned_meals (user_id, day, id);

alter table public.profiles enable row level security;
alter table public.fridge_items enable row level security;
alter table public.planned_meals enable row level security;

create policy "Users manage their profile" on public.profiles
    for all to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);
create policy "Users manage their fridge" on public.fridge_items
    for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "Users manage their meal plan" on public.planned_meals
    for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

grant select, insert, update, delete on public.profiles, public.fridge_items, public.planned_meals to authenticated;
grant usage, select on all sequences in schema public to authenticated;

create or replace function public.create_profile_for_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
    insert into public.profiles (id) values (new.id) on conflict (id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute procedure public.create_profile_for_new_user();

create or replace function public.create_meal_plan(p_day date, p_meals jsonb)
returns setof public.planned_meals
language plpgsql
security invoker set search_path = public
as $$
declare
    current_user_id uuid := auth.uid();
begin
    if current_user_id is null then
        raise exception 'Authentication required';
    end if;
    if exists (select 1 from public.planned_meals where user_id = current_user_id and day = p_day) then
        raise exception 'A plan already exists for this day';
    end if;
    return query
    insert into public.planned_meals (user_id, day, name, calories, protein, carbs, fat)
    select current_user_id, p_day, item.name, item.calories, item.protein, item.carbs, item.fat
    from jsonb_to_recordset(p_meals) as item(
        name text, calories numeric, protein numeric, carbs numeric, fat numeric
    )
    returning *;
end;
$$;

grant execute on function public.create_meal_plan(date, jsonb) to authenticated;
