-- Пользователь и база данных Work Timer (локальная PostgreSQL).
-- Выполняется суперпользователем postgres, БЕЗ транзакции (CREATE DATABASE):
--   psql -X -v ON_ERROR_STOP=1 -v app_password=... -d postgres -f 0000_CreateUserAndDatabase.sql
-- Идемпотентно. Не входит в sql/migrations: миграции 0001+ применяет приложение
-- от имени созданного здесь пользователя.

SELECT format('CREATE ROLE work_timer_app WITH LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'work_timer_app')
\gexec

SELECT format('ALTER ROLE work_timer_app WITH LOGIN PASSWORD %L', :'app_password')
\gexec

SELECT 'CREATE DATABASE work_timer OWNER work_timer_app'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'work_timer')
\gexec

GRANT ALL PRIVILEGES ON DATABASE work_timer TO work_timer_app;

-- Роль anon есть в Supabase всегда; миграции 0001/0002 выдают ей политики RLS.
DO $$ BEGIN CREATE ROLE anon NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;

\connect work_timer
ALTER SCHEMA public OWNER TO work_timer_app;
GRANT ALL ON SCHEMA public TO work_timer_app;
