
-- Default 파티션 생성
CREATE TABLE IF NOT EXISTS public.content_viewing_history_archive_default
PARTITION OF public.content_viewing_history_archive DEFAULT;

-- Step 1: 3개월 이상 지난 데이터 아카이브로 이동
WITH move_rows AS (
    DELETE FROM public.content_viewing_history
    WHERE start_time < NOW() - INTERVAL '3 months'
    RETURNING
        id,
        user_id,
        file_id,
        start_time,
        end_time,
        stay_duration,
        time_stamp::bigint,
        ip_address
)
INSERT INTO public.content_viewing_history_archive (
    id,
    user_id,
    file_id,
    start_time,
    end_time,
    stay_duration,
    time_stamp,
    ip_address
)
SELECT id, user_id, file_id, start_time, end_time, stay_duration, time_stamp, ip_address FROM move_rows;

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

    partition_name text := 'content_viewing_history_archive_' || to_char(next_quarter_start, 'YYYY_MM');

BEGIN
    RAISE NOTICE 'Creating partition: % (% - %)', partition_name, next_quarter_start, next_quarter_end;

    -- 파티션 생성
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS public.%I
        PARTITION OF public.content_viewing_history_archive 
        FOR VALUES FROM (%L) TO (%L);',
        partition_name, next_quarter_start, next_quarter_end);
    
    -- user_id 인덱스 생성
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_%I_user_id 
        ON public.%I (user_id);',
        partition_name, partition_name);
    
    -- start_time 인덱스 생성
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_%I_start_time
        ON public.%I (start_time);',
        partition_name, partition_name);    
END $$;   


-- 파티션 테이블 생성 SQL 쿼리 문(1월 파티션 테이블 생성)
-- DO $$
-- DECLARE
--     this_year text := to_char(NOW(), 'YYYY');
--     partition_name text := 'content_viewing_history_archive_' || this_year || '_01';
--     from_date date := (this_year || '-01-01')::date;
--     to_date date := from_date + INTERVAL '3 months';  -- 3개월 범위
-- BEGIN
--     EXECUTE format('
--         CREATE TABLE IF NOT EXISTS public.%I
--         PARTITION OF public.content_viewing_history_archive
--         FOR VALUES FROM (%L) TO (%L);',
--         partition_name, from_date, to_date);

--     -- 인덱스 생성
--     EXECUTE format('
--         CREATE INDEX IF NOT EXISTS idx_%I_user_id ON public.%I (user_id);',
--         partition_name, partition_name);

--     EXECUTE format('
--         CREATE INDEX IF NOT EXISTS idx_%I_start_time ON public.%I (start_time);',
--         partition_name, partition_name);

-- END $$;
-- DO

-- 파티션 테이블 정보 조회
-- SELECT
--     child.relname AS partition_name,
--     pg_get_expr(child.relpartbound, child.oid) AS partition_range
-- FROM pg_inherits
-- JOIN pg_class parent ON parent.oid = pg_inherits.inhparent
-- JOIN pg_class child  ON child.oid  = pg_inherits.inhrelid
-- WHERE parent.relname = 'content_viewing_history_archive';


-- csv파일을 데이터베이스로 복사
-- COPY content_viewing_history_archive
-- FROM '/home/user_ccp/BepsApi/DB/backup/content_viewing_history_archive_2025_01.csv'
-- WITH (FORMAT csv, HEADER true);

-- 시간과 날짜, 타임존 설정 확인
-- SELECT now(), current_date, current_setting('TIMEZONE');


