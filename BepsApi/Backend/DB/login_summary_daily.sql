CREATE OR REPLACE FUNCTION calculate_work_duration(
    p_login TIMESTAMPTZ,
    p_logout TIMESTAMPTZ,
    p_work_start TIMESTAMPTZ,
    p_work_end TIMESTAMPTZ,
    p_is_weekday BOOLEAN
) RETURNS INTERVAL AS $$
DECLARE
    effective_start TIMESTAMPTZ;
    effective_end TIMESTAMPTZ;
BEGIN
    IF NOT p_is_weekday OR p_logout <= p_login THEN
        RETURN '0'::INTERVAL;
    END IF;

    -- 실제 근무 시간과 겹치는 세션 구간
    effective_start := GREATEST(p_login, p_work_start);
    effective_end := LEAST(p_logout, p_work_end);

    IF effective_end > effective_start THEN
        RETURN effective_end - effective_start;
    ELSE
        RETURN '0'::INTERVAL;
    END IF;
END;
$$ LANGUAGE plpgsql;


-- 매일 집계(UTC 시간 기준이지만 KST 시간에 맞춰서 집계. KST 자정에 맞춘 시간으로 UTC 시간 값 전달 받아서 처리리)
CREATE OR REPLACE FUNCTION aggregate_daily_stats(
    p_start_utc TIMESTAMPTZ
) RETURNS VOID AS $$
DECLARE
    v_work_start_utc TIMESTAMPTZ := p_start_utc + INTERVAL '8 hours'; -- 근무 시작 시간
    v_work_end_utc TIMESTAMPTZ := p_start_utc + INTERVAL '18 hours'; -- 근무 종료 시간
    v_period_value DATE := (p_start_utc AT TIME ZONE 'Asia/Seoul')::DATE; -- 집계 날짜(KST)
    v_is_weekday BOOLEAN := (EXTRACT(DOW FROM p_start_utc AT TIME ZONE 'Asia/Seoul') NOT IN (0, 6)); -- 주말 여부
BEGIN

    -- 4. 사용자별 집계
    INSERT INTO public.login_summary_day (
        period_value,
        company_id, company, department_id, department, user_id, user_name,
        total_duration, worktime_duration, offhour_duration,
        internal_count, external_count
    )
    SELECT
        v_period_value,
        NULL, u.company, NULL, u.department, u.id, u.name,
        COALESCE(SUM(lh.session_duration), '0'::INTERVAL),

        -- 근무 시간: 세션과 근무 시간대가 겹치는 부분
        COALESCE(SUM(calculate_work_duration(
            lh.login_time,
            lh.logout_time,
            v_work_start_utc,
            v_work_end_utc,
            v_is_weekday
        )), '0'::INTERVAL),
        
        -- 근무 외 시간: 전체 세션 - 근무 시간
        COALESCE(SUM(
            (lh.logout_time - lh.login_time) - 
            calculate_work_duration(
                lh.login_time,
                lh.logout_time,
                v_work_start_utc,
                v_work_end_utc,
                v_is_weekday
            )), '0'::INTERVAL),

        COUNT(DISTINCT CASE WHEN r.id IS NOT NULL THEN lh.id END),
        COUNT(DISTINCT CASE WHEN r.id IS NULL THEN lh.id END)
    FROM login_history lh
    LEFT JOIN ip_ranges r ON lh.ip_address::inet BETWEEN r.start_ip::inet AND r.end_ip::inet
    JOIN users u ON lh.user_id = u.id
    WHERE lh.login_time >= p_start_utc AND lh.login_time < p_start_utc + INTERVAL '1 day' AND lh.logout_time IS NOT NULL
    GROUP BY u.company, u.department, u.id, u.name
    ON CONFLICT (period_value, company_key, department_key, user_id_key)
    DO UPDATE SET
        total_duration = EXCLUDED.total_duration,
        worktime_duration = EXCLUDED.worktime_duration,
        offhour_duration = EXCLUDED.offhour_duration,
        internal_count = EXCLUDED.internal_count,
        external_count = EXCLUDED.external_count;

END;
$$ LANGUAGE plpgsql;


-- ================================
-- 📌 매일 집계 (UTC 시간 기준)
-- ================================
-- CREATE OR REPLACE FUNCTION aggregate_daily_stats(
--     p_date DATE
-- ) RETURNS VOID AS $$
-- DECLARE
--     v_work_start_utc TIMESTAMP := (p_date + INTERVAL '8 hours' - INTERVAL '9 hours')::TIMESTAMP; -- 근무 시작 시간
--     v_work_end_utc TIMESTAMP := (p_date + INTERVAL '18 hours' - INTERVAL '9 hours')::TIMESTAMP; -- 근무 종료 시간
--     v_is_weekday BOOLEAN := (EXTRACT(DOW FROM p_date) NOT IN (0,6));                       -- 주말 여부
-- BEGIN

--     -- 0. 기존 데이터 삭제
--     DELETE FROM public.login_summary_day
--     WHERE period_value = p_date;
--     -- ON CONFLICT 사용하려 했으나, Unique 제약 조건 중복으로 인해 삭제

--     -- 1. 전체 범위(전체) 집계
--     INSERT INTO public.login_summary_day (
--         period_value, scope,
--         total_duration, worktime_duration, offhour_duration,
--         internal_count, external_count
--     )
--     SELECT
--         p_date, 'all',
--         COALESCE(SUM(session_duration), '0'::INTERVAL),

--         -- 근무 시간: 세션과 근무 시간대가 겹치는 부분
--         COALESCE(SUM(calculate_work_duration(
--             login_time,
--             COALESCE(logout_time, login_time + INTERVAL '5 minutes'),
--             v_work_start_utc,
--             v_work_end_utc,
--             v_is_weekday
--         )), '0'::INTERVAL),
        
--         -- 근무 외 시간: 전체 세션 - 근무 시간
--         COALESCE(SUM(
--             (COALESCE(logout_time, login_time + INTERVAL '5 minutes') - login_time) - 
--             calculate_work_duration(
--                 login_time,
--                 COALESCE(logout_time, login_time + INTERVAL '5 minutes'),
--                 v_work_start_utc,
--                 v_work_end_utc,
--                 v_is_weekday
--             )), '0'::INTERVAL),

--         COUNT(DISTINCT CASE WHEN ip_address LIKE '61.%' OR ip_address LIKE '172.%' THEN id END),
--         COUNT(DISTINCT CASE WHEN NOT (ip_address LIKE '61.%' OR ip_address LIKE '172.%') THEN id END)

--     FROM login_history
--     WHERE login_time::DATE = p_date;

--     -- 2. 회사별 집계
--     INSERT INTO public.login_summary_day (
--         period_value, scope,
--         company_id, company,
--         total_duration, worktime_duration, offhour_duration,
--         internal_count, external_count
--     )
--     SELECT
--         p_date, 'company',
--         NULL, u.company,
--         COALESCE(SUM(lh.session_duration), '0'::INTERVAL),

--         -- 근무 시간: 세션과 근무 시간대가 겹치는 부분
--         COALESCE(SUM(calculate_work_duration(
--             lh.login_time,
--             COALESCE(lh.logout_time, lh.login_time + INTERVAL '5 minutes'),
--             v_work_start_utc,
--             v_work_end_utc,
--             v_is_weekday
--         )), '0'::INTERVAL),
        
--         -- 근무 외 시간: 전체 세션 - 근무 시간
--         COALESCE(SUM(
--             (COALESCE(lh.logout_time, lh.login_time + INTERVAL '5 minutes') - lh.login_time) - 
--             calculate_work_duration(
--                 lh.login_time,
--                 COALESCE(lh.logout_time, lh.login_time + INTERVAL '5 minutes'),
--                 v_work_start_utc,
--                 v_work_end_utc,
--                 v_is_weekday
--             )), '0'::INTERVAL),

--         COUNT(DISTINCT CASE WHEN lh.ip_address LIKE '61.%' OR lh.ip_address LIKE '172.%' THEN lh.id END),
--         COUNT(DISTINCT CASE WHEN NOT (lh.ip_address LIKE '61.%' OR lh.ip_address LIKE '172.%') THEN lh.id END)
--     FROM login_history lh
--     JOIN users u ON lh.user_id = u.id
--     WHERE lh.login_time::DATE = p_date
--     GROUP BY u.company;
    

--     -- 3. 부서별 집계
--     INSERT INTO public.login_summary_day (
--         period_value, scope,
--         company_id, company, department_id, department,
--         total_duration, worktime_duration, offhour_duration,
--         internal_count, external_count
--     )
--     SELECT
--         p_date, 'department',
--         NULL, u.company, NULL, u.department,
--         COALESCE(SUM(lh.session_duration), '0'::INTERVAL),
        
--         -- 근무 시간: 세션과 근무 시간대가 겹치는 부분
--         COALESCE(SUM(calculate_work_duration(
--             lh.login_time,
--             COALESCE(lh.logout_time, lh.login_time + INTERVAL '5 minutes'),
--             v_work_start_utc,
--             v_work_end_utc,
--             v_is_weekday
--         )), '0'::INTERVAL),
        
--         -- 근무 외 시간: 전체 세션 - 근무 시간
--         COALESCE(SUM(
--             (COALESCE(lh.logout_time, lh.login_time + INTERVAL '5 minutes') - lh.login_time) - 
--             calculate_work_duration(
--                 lh.login_time,
--                 COALESCE(lh.logout_time, lh.login_time + INTERVAL '5 minutes'),
--                 v_work_start_utc,
--                 v_work_end_utc,
--                 v_is_weekday
--             )), '0'::INTERVAL),

--         COUNT(DISTINCT CASE WHEN lh.ip_address LIKE '61.%' OR lh.ip_address LIKE '172.%' THEN lh.id END),
--         COUNT(DISTINCT CASE WHEN NOT (lh.ip_address LIKE '61.%' OR lh.ip_address LIKE '172.%') THEN lh.id END)
--     FROM login_history lh
--     JOIN users u ON lh.user_id = u.id
--     WHERE lh.login_time::DATE = p_date
--     GROUP BY u.company, u.department;

--     -- 4. 사용자별 집계
--     INSERT INTO public.login_summary_day (
--         period_value, scope,
--         company_id, company, department_id, department, user_id, user_name,
--         total_duration, worktime_duration, offhour_duration,
--         internal_count, external_count
--     )
--     SELECT
--         p_date, 'user',
--         NULL, u.company, NULL, u.department, u.id, u.name,
--         COALESCE(SUM(lh.session_duration), '0'::INTERVAL),

--         -- 근무 시간: 세션과 근무 시간대가 겹치는 부분
--         COALESCE(SUM(calculate_work_duration(
--             lh.login_time,
--             COALESCE(lh.logout_time, lh.login_time + INTERVAL '5 minutes'),
--             v_work_start_utc,
--             v_work_end_utc,
--             v_is_weekday
--         )), '0'::INTERVAL),
        
--         -- 근무 외 시간: 전체 세션 - 근무 시간
--         COALESCE(SUM(
--             (COALESCE(lh.logout_time, lh.login_time + INTERVAL '5 minutes') - lh.login_time) - 
--             calculate_work_duration(
--                 lh.login_time,
--                 COALESCE(lh.logout_time, lh.login_time + INTERVAL '5 minutes'),
--                 v_work_start_utc,
--                 v_work_end_utc,
--                 v_is_weekday
--             )), '0'::INTERVAL),

--         COUNT(DISTINCT CASE WHEN lh.ip_address LIKE '61.%' OR lh.ip_address LIKE '172.%' THEN lh.id END),
--         COUNT(DISTINCT CASE WHEN NOT (lh.ip_address LIKE '61.%' OR lh.ip_address LIKE '172.%') THEN lh.id END)
--     FROM login_history lh
--     JOIN users u ON lh.user_id = u.id
--     WHERE lh.login_time::DATE = p_date
--     GROUP BY u.company, u.department, u.id, u.name;

-- END;
-- $$ LANGUAGE plpgsql;
\!

-- ================================
-- 📌 함수 등록록
-- ================================
-- sudo -u postgres psql -d beps -f Backend/DB/login_summary_day.sql

-- ================================
-- 📌 함수 실행
-- ================================
-- 1. 특정 날짜에 대한 집계 실행
--SELECT aggregate_daily_stats('2025-04-01');
-- 2. 특정 날짜에 대한 집계 실행 (KST 자정에 맞춘 시간을 UTC 변환해서 전달)
-- SELECT aggregate_daily_stats(
--   (TIMESTAMP '2025-04-02' AT TIME ZONE 'Asia/Seoul' - INTERVAL '1 day') AT TIME ZONE 'UTC'
-- );


-- ================================
-- 📌 인덱스 제거
-- ================================
--  DROP INDEX IF EXISTS login_summary_day_unique_department_idx;

-- ================================
-- 📌 인덱스 만들기
-- ================================
-- CREATE UNIQUE INDEX login_summary_day_unique_user_idx ON login_summary_day (period_value, scope, company, department, user_id) WHERE scope = 'user';

-- ================================
-- 📌 3월 23일에 b23009 사용자의 로그인 기록을 KTS 시간으로 변환하여 조회
-- ================================
-- SELECT
--   id,
--   user_id,
--   ip_address,
--   login_time AT TIME ZONE 'Asia/Seoul' AS login_time_kst,
--   logout_time AT TIME ZONE 'Asia/Seoul' AS logout_time_kst,
--   session_duration,
--   time_stamp
-- FROM login_history
-- WHERE user_id = 'b23009'
--   AND login_time::date = '2025-03-28';

-- ========================
-- 📌 3월 28일에 로그인한 모든 사용자 조회(KST 시간대로 변환환)
-- ========================
-- SELECT *
-- FROM login_history
-- WHERE (login_time AT TIME ZONE 'Asia/Seoul')::date = DATE '2025-03-28';


-- ================================
-- 📌 매일 1시에 집계 실행: UTC 기준. 한국(KST)은 UTC+9
-- ================================
-- SELECT cron.schedule(
--   'daily_login_summary',
--   '0 16 * * *',
--   --$$SELECT aggregate_daily_stats(current_date - INTERVAL '1 day');$$  
--   $$SELECT aggregate_daily_stats((DATE_TRUNC('day', now() AT TIME ZONE 'Asia/Seoul') - INTERVAL '1 day') AT TIME ZONE 'UTC');$$
-- );

