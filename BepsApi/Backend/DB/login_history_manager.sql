-- Default 파티션 생성
CREATE TABLE IF NOT EXISTS public.login_history_archive_default
PARTITION OF public.login_history_archive DEFAULT;

-- Step 1: 3개월 이상 지난 데이터 아카이브로 이동
WITH move_rows AS (
    DELETE FROM public.login_history
    WHERE login_time < NOW() - INTERVAL '3 months'
    RETURNING
        id,
        user_id,
        ip_address,
        login_time,
        logout_time,
        session_duration,
        time_stamp::bigint
)
INSERT INTO public.login_history_archive (
    id,
    user_id,
    ip_address,
    login_time,
    logout_time,
    session_duration,
    time_stamp
)
SELECT id, user_id, ip_address, login_time, logout_time, session_duration, time_stamp FROM move_rows;

-- Step 2: 다음 분기 파티션 자동 생성(파티셔닝된 아카이브 테이블)
SET TIMEZONE TO 'Asia/Seoul';
DO $$
DECLARE
    -- 다음 분기 첫 달 계산
    base_month date := date_trunc('month', CURRENT_DATE);  -- 현재 월의 첫날
    next_quarter_month int := ((extract(month from base_month)::int - 1) / 3 + 1) * 3 + 1;
    next_quarter_year int := extract(year from base_month)::int + CASE WHEN next_quarter_month > 12 THEN 1 ELSE 0 END;
    next_quarter_month_adj int := CASE WHEN next_quarter_month > 12 THEN next_quarter_month - 12 ELSE next_quarter_month END;

    next_quarter_start date := make_date(next_quarter_year, next_quarter_month_adj, 1);
    next_quarter_end date := next_quarter_start + INTERVAL '3 month';

    partition_name text := 'login_history_archive_' || to_char(next_quarter_start, 'YYYY_MM');

BEGIN
    RAISE NOTICE 'Creating partition: % (% - %)', partition_name, next_quarter_start, next_quarter_end;

    -- 파티션 생성
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS public.%I
        PARTITION OF public.login_history_archive 
        FOR VALUES FROM (%L) TO (%L);',
        partition_name, next_quarter_start, next_quarter_end);
    
    -- user_id 인덱스 생성
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_%I_user_id 
        ON public.%I (user_id);',
        partition_name, partition_name);
    
    -- login_time 인덱스 생성
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_%I_login_time
        ON public.%I (login_time);',
        partition_name, partition_name);    
END $$;  