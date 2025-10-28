CREATE OR REPLACE FUNCTION aggregate_learning_summary_daily(
    p_start_utc TIMESTAMPTZ
) RETURNS VOID AS $$
DECLARE
    v_start_value DATE := (p_start_utc AT TIME ZONE 'Asia/Seoul')::DATE;
BEGIN
    -- 사용자별 집계
    INSERT INTO learning_summary_day (
        stat_date, company_id, company, department_id, department, user_id, user_name, channel_id, channel_name, total_duration
    )
    SELECT
        v_start_value, NULL, u.company, NULL, u.department, u.id, u.name, c.id, c.name,
        SUM(cvh.stay_duration)
    FROM content_viewing_history cvh
    JOIN users u ON u.id = cvh.user_id
    -- 폴더 ID 추출: content_rel_page_details, content_rel_pages를 조인해서 폴더 ID를 가져옴
    LEFT JOIN content_rel_pages p ON cvh.file_type = 'page' AND cvh.file_id = p.id
    LEFT JOIN content_rel_page_details d ON cvh.file_type = 'detail' AND cvh.file_id = d.id
    LEFT JOIN content_rel_pages dp ON d.page_id = dp.id
    LEFT JOIN content_rel_folders f ON f.id = COALESCE(p.folder_id, dp.folder_id)
    -- 폴더 ID를 통해 channel 추출
    JOIN content_rel_channels c ON c.id = f.channel_id
    -- 기간 필터링
    WHERE cvh.start_time >= p_start_utc AND cvh.start_time < p_start_utc + INTERVAL '1 day'
    GROUP BY u.company, u.department, u.id, u.name, c.id, c.name
    HAVING SUM(cvh.stay_duration) > INTERVAL '0'
    ON CONFLICT(stat_date, company_key, department_key, user_id_key, channel_key)
    DO UPDATE SET total_duration = EXCLUDED.total_duration;

EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Error in aggregate_learning_summary_daily: %', SQLERRM;
        RAISE;  

END;
$$ LANGUAGE plpgsql;



-- SELECT aggregate_learning_summary_daily((DATE_TRUNC('day', '2025-03-13' AT TIME ZONE 'Asia/Seoul') - INTERVAL '1 day') AT TIME ZONE 'Asia/Seoul');


-- top_pages 쿼리
-- SELECT f.file_id, f.file_name, COUNT(*) AS view_count
-- FROM content_viewing_history_archive cvh
-- JOIN files f ON f.file_id = cvh.file_id
-- JOIN users u ON u.id = cvh.user_id
-- WHERE cvh.start_time >= :start_date AND cvh.start_time < :end_date
--   AND (:company IS NULL OR u.company = :company)
--   AND (:department IS NULL OR u.department = :department)
--   AND (:user_id IS NULL OR u.id = :user_id)
-- GROUP BY f.file_id, f.file_name
-- ORDER BY view_count DESC
-- LIMIT 10;


CREATE OR REPLACE FUNCTION aggregate_learning_summary_quarterly(p_year INT, p_quarter INT)
RETURNS VOID AS $$
DECLARE
    v_start DATE;
    v_end DATE;
    v_period_value TEXT := format('%s-Q%s', p_year, p_quarter);
BEGIN
    v_start := make_date(p_year, (p_quarter - 1) * 3 + 1, 1);
    v_end := (v_start + interval '3 months - 1 day')::DATE;

    -- 사용자별 집계
    INSERT INTO learning_summary_agg (
        period_type, period_value, company_id, company, department_id, department, user_id, user_name, channel_id, channel_name, total_duration
    )
    SELECT
        'quarter', v_period_value, NULL, company, NULL, department, user_id, user_name, channel_id, channel_name, SUM(total_duration)
    FROM learning_summary_day
    WHERE stat_date >= v_start AND stat_date <= v_end
    GROUP BY company, department, user_id, user_name, channel_id, channel_name
    HAVING SUM(total_duration) > INTERVAL '0'
    ON CONFLICT (period_value, company_key, department_key, user_id_key, channel_key)
    DO UPDATE SET
        total_duration = EXCLUDED.total_duration;

EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Error in aggregate_learning_summary_quaterly: %', SQLERRM;
        RAISE; 

END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION aggregate_learning_summary_halfyearly(p_year INT, p_halfyear INT)
RETURNS VOID AS $$
DECLARE
    v_quarters TEXT[];
    v_period_value TEXT := format('%s-H%s', p_year, p_halfyear);
BEGIN
    v_quarters := CASE WHEN p_halfyear = 1
                        THEN ARRAY[format('%s-Q1', p_year), format('%s-Q2', p_year)]
                        ELSE ARRAY[format('%s-Q3', p_year), format('%s-Q4', p_year)]
                  END;

    -- 사용자별 집계
    INSERT INTO learning_summary_agg (
        period_type, period_value, company_id, company, department_id, department, user_id, user_name, channel_id, channel_name, total_duration
    )
    SELECT
        'half', v_period_value, NULL, company, NULL, department, user_id, user_name, channel_id, channel_name, SUM(total_duration)
    FROM learning_summary_agg
    WHERE period_type = 'quarter' AND period_value = ANY(v_quarters)
    GROUP BY company, department, user_id, user_name, channel_id, channel_name
    HAVING SUM(total_duration) > INTERVAL '0'
    ON CONFLICT (period_value, company_key, department_key, user_id_key, channel_key)
    DO UPDATE SET
        total_duration = EXCLUDED.total_duration;

EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Error in aggregate_learning_summary_halfyearly: %', SQLERRM;
        RAISE;  

END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION aggregate_learning_summary_yearly(p_year INT)
RETURNS VOID AS $$
DECLARE
    v_period_value TEXT := format('%s', p_year);
BEGIN

    -- 사용자별 집계
    INSERT INTO learning_summary_agg (
        period_type, period_value, company_id, company, department_id, department, user_id, user_name, channel_id, channel_name, total_duration
    )
    SELECT
        'year', v_period_value, NULL, company, NULL, department, user_id, user_name, channel_id, channel_name, SUM(total_duration)
    FROM learning_summary_agg   
    WHERE period_type = 'half' AND period_value LIKE format('%s-H%%', p_year)
    GROUP BY company, department, user_id, user_name, channel_id, channel_name
    HAVING SUM(total_duration) > INTERVAL '0'
    ON CONFLICT (period_value, company_key, department_key, user_id_key, channel_key)
    DO UPDATE SET
        total_duration = EXCLUDED.total_duration;

EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Error in aggregate_learning_summary_yearly: %', SQLERRM;
        RAISE; 

END;
$$ LANGUAGE plpgsql;
