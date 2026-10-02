-- Перенос оставшихся таблиц с префиксом wh_ из Supabase в PostgreSQL:
-- wh_invite_tokens, wh_password_resets, wh_user_profiles.
-- Структура взята из Supabase (PostgREST OpenAPI-схема). Эти таблицы не используются
-- кодом текущего приложения (timer.py/db_backend.py) — переносится только структура,
-- без данных: anon-ключ Supabase не имеет SELECT-политики на эти таблицы, поэтому
-- реальные строки через REST API недоступны.
-- Запустите этот запрос в Supabase → SQL Editor (или psql) для целевой PostgreSQL.

CREATE TABLE IF NOT EXISTS public.wh_user_profiles (
    id         UUID        PRIMARY KEY,
    role       TEXT        NOT NULL DEFAULT 'viewer',
    invited_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.wh_invite_tokens (
    token      TEXT        PRIMARY KEY,
    email      TEXT        NOT NULL,
    invited_by UUID,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.wh_password_resets (
    token      TEXT        PRIMARY KEY,
    user_id    UUID        NOT NULL,
    email      TEXT        NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- В Supabase эти таблицы защищены RLS без anon-политик (доступ только через
-- service_role на бэкенде) — включаем RLS и не добавляем политики для anon,
-- сохраняя тот же уровень защиты в целевой PostgreSQL.
ALTER TABLE public.wh_user_profiles   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wh_invite_tokens   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wh_password_resets ENABLE ROW LEVEL SECURITY;

INSERT INTO public.schema_migrations (name, applied_at)
VALUES ('0004_MigrateRemainingWhTables', now()::timestamptz)
ON CONFLICT (name) DO UPDATE SET applied_at = now()::timestamptz;
