-- Таблица планового количества рабочих дней/часов по производственному календарю
-- Источник данных: https://www.consultant.ru/law/ref/calendar/proizvodstvennye/2026/ (40-часовая рабочая неделя)
-- Запустите этот запрос в Supabase → SQL Editor

CREATE TABLE IF NOT EXISTS public.wh_plan_work_hourses (
    id         BIGSERIAL PRIMARY KEY,
    year       INTEGER      NOT NULL,
    month      INTEGER      NOT NULL CHECK (month BETWEEN 1 AND 12),
    work_days  INTEGER      NOT NULL,
    work_hours NUMERIC(6,2) NOT NULL,
    UNIQUE (year, month)
);

INSERT INTO public.wh_plan_work_hourses (year, month, work_days, work_hours) VALUES
    (2026, 1,  15, 120.0),
    (2026, 2,  19, 152.0),
    (2026, 3,  21, 168.0),
    (2026, 4,  22, 175.0),
    (2026, 5,  19, 151.0),
    (2026, 6,  21, 167.0),
    (2026, 7,  23, 184.0),
    (2026, 8,  21, 168.0),
    (2026, 9,  22, 176.0),
    (2026, 10, 22, 176.0),
    (2026, 11, 20, 159.0),
    (2026, 12, 22, 176.0)
ON CONFLICT (year, month) DO UPDATE SET
    work_days  = EXCLUDED.work_days,
    work_hours = EXCLUDED.work_hours;

ALTER TABLE public.wh_plan_work_hourses ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "wh_plan_work_hourses_anon_select" ON public.wh_plan_work_hourses;
CREATE POLICY "wh_plan_work_hourses_anon_select"
    ON public.wh_plan_work_hourses
    FOR SELECT
    TO anon
    USING (true);

DROP POLICY IF EXISTS "wh_plan_work_hourses_anon_insert" ON public.wh_plan_work_hourses;
CREATE POLICY "wh_plan_work_hourses_anon_insert"
    ON public.wh_plan_work_hourses
    FOR INSERT
    TO anon
    WITH CHECK (true);

DROP POLICY IF EXISTS "wh_plan_work_hourses_anon_update" ON public.wh_plan_work_hourses;
CREATE POLICY "wh_plan_work_hourses_anon_update"
    ON public.wh_plan_work_hourses
    FOR UPDATE
    TO anon
    USING (true)
    WITH CHECK (true);

INSERT INTO public.schema_migrations (name, applied_at)
VALUES ('0002_CreatePlanWorkHoursTable', now()::timestamptz)
ON CONFLICT (name) DO UPDATE SET applied_at = now()::timestamptz;
