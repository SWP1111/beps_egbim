CREATE OR REPLACE FUNCTION create_login_summary_quarter_partition()
RETURNS VOID AS $$
DECLARE
    base_month DATE := date_trunc('month', CURRENT_DATE);
    next_quarter_month INT := ((extract(month from base_month)::int - 1) / 3 + 1) * 3 + 1;
    next_quarter_year INT := extract(year from base_month)::int + CASE WHEN next_quarter_month > 12 THEN 1 ELSE 0 END;
    next_quarter_month_adj INT := CASE WHEN next_quarter_month > 12 THEN next_quarter_month - 12 ELSE next_quarter_month END;

    partition_start DATE := make_date(next_quarter_year, next_quarter_month_adj, 1);
    partition_end DATE := partition_start + INTERVAL '3 month';
    partition_name TEXT := 'login_summary_day_' || to_char(partition_start, 'YYYY_MM');
BEGIN
    RAISE NOTICE 'Creating partition % from % to %', partition_name, partition_start, partition_end;

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I
        PARTITION OF login_summary_day
        FOR VALUES FROM (%L) TO (%L);',
        partition_name, partition_start, partition_end
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION create_learning_summary_quarter_partition()
RETURNS VOID AS $$
DECLARE
    base_month DATE := date_trunc('month', CURRENT_DATE);
    next_quarter_month INT := ((extract(month from base_month)::int - 1) / 3 + 1) * 3 + 1;
    next_quarter_year INT := extract(year from base_month)::int + CASE WHEN next_quarter_month > 12 THEN 1 ELSE 0 END;
    next_quarter_month_adj INT := CASE WHEN next_quarter_month > 12 THEN next_quarter_month - 12 ELSE next_quarter_month END;

    partition_start DATE := make_date(next_quarter_year, next_quarter_month_adj, 1);
    partition_end DATE := partition_start + INTERVAL '3 month';
    partition_name TEXT := 'learning_summary_day_' || to_char(partition_start, 'YYYY_MM');
BEGIN
    RAISE NOTICE 'Creating partition % from % to %', partition_name, partition_start, partition_end;

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I
        PARTITION OF learning_summary_day
        FOR VALUES FROM (%L) TO (%L);',
        partition_name, partition_start, partition_end
    );
END;
$$ LANGUAGE plpgsql;

-- 함수 등록
-- sudo -u postgres psql -d beps -f Backend/DB/login_summary_partition.sql

-- 스케줄 등록. 주기적으로 함수 실행
-- SELECT cron.schedule(
--   'create_half_partition',
--   '0 18 5 1,7 *',  -- 매년 1/5, 7/5, UTC 18시 (KST 새벽 3시)
--   $$SELECT create_half_year_partition();$$
-- );


-- 수동으로 PARTION 생성
-- CREATE TABLE login_summary_day_2025_h1
-- PARTITION OF login_summary_day
-- FOR VALUES FROM ('2025-01-01') TO ('2025-07-01');


-- UTC, KST 시간 표시
-- SELECT 
--   login_time,  -- UTC 시각
--   login_time AT TIME ZONE 'Asia/Seoul' AS login_time_kst  -- KST 시각
-- FROM login_history
-- WHERE 
--   login_time AT TIME ZONE 'Asia/Seoul' >= '2025-04-02 00:00:00'
--   AND login_time AT TIME ZONE 'Asia/Seoul' < '2025-04-03 00:00:00';


-- 1회성 실행
-- DO $$
-- DECLARE
--     -- 기준: 현재 날짜
--     base_date DATE := date_trunc('month', CURRENT_DATE)::DATE;

--     -- 다음 반기 계산
--     next_half_start DATE;
--     next_half_end DATE;
--     partition_name TEXT;

--     half_num INT;
--     half_year INT;
-- BEGIN
--     -- 다음 반기 시작 월 계산 (1월 또는 7월)
--     IF EXTRACT(MONTH FROM base_date) < 7 THEN
--         next_half_start := make_date(EXTRACT(YEAR FROM base_date)::INT, 7, 1);
--     ELSE
--         next_half_start := make_date(EXTRACT(YEAR FROM base_date)::INT + 1, 1, 1);
--     END IF;

--     next_half_end := next_half_start + INTERVAL '6 months';

--     -- 파티션 이름: 예) login_summary_day_2024h2
--     half_year := EXTRACT(YEAR FROM next_half_start)::INT;
--     half_num := CASE WHEN EXTRACT(MONTH FROM next_half_start) = 1 THEN 1 ELSE 2 END;
--     partition_name := format('login_summary_day_%s_h%s', half_year, half_num);

--     -- 파티션 생성
--     RAISE NOTICE 'Creating partition % from % to %', partition_name, next_half_start, next_half_end;

--     EXECUTE format('
--         CREATE TABLE IF NOT EXISTS %I
--         PARTITION OF login_summary_day
--         FOR VALUES FROM (%L) TO (%L);',
--         partition_name, next_half_start, next_half_end
--     );
-- END $$;



-- PostgreSQL에서 반기별 파티션을 생성하는 함수
-- 이 함수는 매년 1월과 7월에 반기별 파티션을 생성합니다.
-- CREATE OR REPLACE FUNCTION create_half_year_partition()
-- RETURNS VOID AS $$
-- DECLARE
--     -- 기준: 현재 날짜
--     base_date DATE := date_trunc('month', CURRENT_DATE)::DATE;

--     -- 다음 반기 계산
--     next_half_start DATE;
--     next_half_end DATE;
--     partition_name TEXT;

--     half_num INT;
--     half_year INT;
-- BEGIN
--     -- 다음 반기 시작 월 계산 (1월 또는 7월)
--     IF EXTRACT(MONTH FROM base_date) < 7 THEN
--         next_half_start := make_date(EXTRACT(YEAR FROM base_date)::INT, 7, 1);
--     ELSE
--         next_half_start := make_date(EXTRACT(YEAR FROM base_date)::INT + 1, 1, 1);
--     END IF;

--     next_half_end := next_half_start + INTERVAL '6 months';

--     -- 파티션 이름: 예) login_summary_day_2024h2
--     half_year := EXTRACT(YEAR FROM next_half_start)::INT;
--     half_num := CASE WHEN EXTRACT(MONTH FROM next_half_start) = 1 THEN 1 ELSE 2 END;
--     partition_name := format('login_summary_day_%s_h%s', half_year, half_num);

--     -- 파티션 생성
--     RAISE NOTICE 'Creating partition % from % to %', partition_name, next_half_start, next_half_end;

--     EXECUTE format('
--         CREATE TABLE IF NOT EXISTS %I
--         PARTITION OF login_summary_day
--         FOR VALUES FROM (%L) TO (%L);',
--         partition_name, next_half_start, next_half_end
--     );
-- END;
-- $$ LANGUAGE plpgsql;