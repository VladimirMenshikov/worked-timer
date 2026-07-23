-- Создание таблицы для логирования рабочих сессий
-- Запустите этот запрос в Supabase → SQL Editor

CREATE TABLE wh_work_log (
    id           BIGSERIAL    PRIMARY KEY,
    session_id   UUID         NOT NULL,
    operation    VARCHAR(6)   NOT NULL CHECK (operation IN ('start', 'pause', 'resume', 'stop')),
    task         TEXT,
    event_time   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    elapsed_time TEXT
);

CREATE INDEX idx_wh_work_log_session    ON wh_work_log (session_id);
CREATE INDEX idx_wh_work_log_event_time ON wh_work_log (event_time DESC);
