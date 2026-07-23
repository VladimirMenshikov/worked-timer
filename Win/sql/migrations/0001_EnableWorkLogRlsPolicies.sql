-- Включение RLS и добавление политик для wh_work_log
-- Приложение использует anon-ключ и делает только INSERT (старт/стоп таймера) и SELECT (статистика, отчёты)
-- Запустите этот запрос в Supabase → SQL Editor

ALTER TABLE public.wh_work_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "wh_work_log_anon_insert" ON public.wh_work_log;
CREATE POLICY "wh_work_log_anon_insert"
    ON public.wh_work_log
    FOR INSERT
    TO anon
    WITH CHECK (true);

DROP POLICY IF EXISTS "wh_work_log_anon_select" ON public.wh_work_log;
CREATE POLICY "wh_work_log_anon_select"
    ON public.wh_work_log
    FOR SELECT
    TO anon
    USING (true);

INSERT INTO public.schema_migrations (name, applied_at)
VALUES ('0001_EnableWorkLogRlsPolicies', now()::timestamptz)
ON CONFLICT (name) DO UPDATE SET applied_at = now()::timestamptz;
