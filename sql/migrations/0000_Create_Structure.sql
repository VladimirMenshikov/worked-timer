-- Начальная структура базы данных Work Timer
-- Запустите этот запрос в Supabase → SQL Editor

CREATE TABLE IF NOT EXISTS public.schema_migrations (
    name         text        PRIMARY KEY,
    applied_at   timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS public.wh_work_log (
    id           BIGSERIAL    PRIMARY KEY,
    session_id   UUID         NOT NULL,
    operation    VARCHAR(5)   NOT NULL CHECK (operation IN ('start', 'stop')),
    task         TEXT,
    event_time   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    elapsed_time TEXT
);

CREATE INDEX IF NOT EXISTS idx_wh_work_log_session    ON public.wh_work_log (session_id);
CREATE INDEX IF NOT EXISTS idx_wh_work_log_event_time ON public.wh_work_log (event_time DESC);

INSERT INTO public.schema_migrations (name, applied_at)
VALUES ('0000_Create_Structure', now()::timestamptz)
ON CONFLICT (name) DO UPDATE SET applied_at = now()::timestamptz;
