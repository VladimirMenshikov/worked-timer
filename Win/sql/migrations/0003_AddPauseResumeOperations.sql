-- Расширение wh_work_log операциями pause/resume для постановки задачи на паузу
-- Запустите этот запрос в Supabase → SQL Editor

ALTER TABLE public.wh_work_log
    ALTER COLUMN operation TYPE VARCHAR(6);

ALTER TABLE public.wh_work_log
    DROP CONSTRAINT IF EXISTS wh_work_log_operation_check;

ALTER TABLE public.wh_work_log
    ADD CONSTRAINT wh_work_log_operation_check
    CHECK (operation IN ('start', 'pause', 'resume', 'stop'));

INSERT INTO public.schema_migrations (name, applied_at)
VALUES ('0003_AddPauseResumeOperations', now()::timestamptz)
ON CONFLICT (name) DO UPDATE SET applied_at = now()::timestamptz;
