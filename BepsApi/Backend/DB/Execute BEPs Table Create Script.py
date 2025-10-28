# psycopg2 설치가 우선되어야 함
# 터미널에서 아래 명령어 실행
# pip install psycopg2

import psycopg2
from psycopg2 import sql

# PostgreSQL 데이터베이스에 연결
connection = psycopg2.connect(
    host="172.16.10.191",   # 데이터베이스 호스트
    port=15432,             # 데이터베이스 포트
    database="postgres",    # 데이터베이스 이름
    user="postgres",    # 데이터베이스 사용자 이름
    password="postgres" # 데이터베이스 사용자 비밀번호
)

#autocommit 활성화
connection.autocommit = True

# 커서 생성
cursor = connection.cursor()

try:
    # 데이터베이스 생성
    cursor.execute("""
        CREATE DATABASE beps
        WITH 
        OWNER = postgres
        ENCODING = 'UTF8'
        LC_COLLATE = 'en_US.UTF-8'
        LC_CTYPE = 'en_US.UTF-8'
        LOCALE_PROVIDER = 'libc'
        TABLESPACE = pg_default
        CONNECTION LIMIT = -1
        IS_TEMPLATE = False;
    """)
except Exception as e:
    print(f"Error: {e}")
finally:
    cursor.close()
    connection.close()

# beps 데이터베이스에 연결
connection = psycopg2.connect(
    host="172.16.10.191",   # 데이터베이스 호스트
    port=15432,
    database="beps",    # 데이터베이스 이름
    user="postgres",    # 데이터베이스 사용자 이름
    password="postgres" # 데이터베이스 사용자 비밀번호
)

# 커서 생성
cursor = connection.cursor()

try:

    #region content_access_groups 테이블
    content_access_groups_queries =  """
        CREATE TABLE IF NOT EXISTS public.content_access_groups (
            access_group_id integer NOT NULL,       -- 접근 그룹 ID                   
            group_name text,                        -- 그룹 이름
            time_stamp bigint,
            CONSTRAINT content_access_groups_pkey PRIMARY KEY (access_group_id)
        );
        """
    
    # ContentAccessGroups_AccessGroupId_seq 시퀀스 생성 쿼리
    content_access_groups_sequence = ["""
        CREATE SEQUENCE public.content_access_groups_id_seq
        AS integer
        START WITH 1
        INCREMENT BY 1
        NO MINVALUE
        NO MAXVALUE
        CACHE 1;
        """,
        """
        ALTER SEQUENCE public.content_access_groups_id_seq OWNER TO postgres;
        """,
        """
        ALTER SEQUENCE public.content_access_groups_id_seq OWNED BY public.content_access_groups.access_group_id;
        """,
        """
        ALTER TABLE ONLY public.content_access_groups ALTER COLUMN access_group_id SET DEFAULT nextval('public.content_access_groups_id_seq'::regclass);
        """,
        # """
        # SELECT pg_catalog.setval('public.content_access_groups_id_seq', 1, false);
        # """,
    ]

    #endregion
    
    #region access_group_contents 테이블
    access_group_contents_queries ="""
        CREATE TABLE IF NOT EXISTS public.access_group_contents (
            access_group_id integer NOT NULL,
            folder_id integer NOT NULL,
            time_stamp bigint,
            CONSTRAINT access_group_contents_pkey PRIMARY KEY (access_group_id, folder_id),
            CONSTRAINT access_group_id FOREIGN KEY (access_group_id) REFERENCES public.content_access_groups(access_group_id) ON DELETE CASCADE,
            CONSTRAINT folder_id FOREIGN KEY (folder_id) REFERENCES public.content_rel_folders(id) ON DELETE CASCADE
        );
        """
    #endregion

    #region roles 테이블
    roles_queries = """
        CREATE TABLE public.roles (
        role_id integer NOT NULL,
        role_name text NOT NULL,
        time_stamp bigint,
        description jsonb,
        CONSTRAINT roles_pkey PRIMARY KEY (role_id)
        );  
        """

    # Roles_RoleId_seq 시퀀스 생성 쿼리
    roles_sequence = [
        """
        CREATE SEQUENCE public.roles_role_id_seq
            AS integer
            START WITH 1
            INCREMENT BY 1
            NO MINVALUE
            NO MAXVALUE
            CACHE 1;
        """,
        """
        ALTER SEQUENCE public.roles_role_id_seq OWNED BY public.roles.role_id;
        """,
        """
        ALTER TABLE ONLY public.roles ALTER COLUMN role_id SET DEFAULT nextval('public.roles_role_id_seq'::regclass);
        """,
        # """
        # SELECT pg_catalog.setval('public.roles_role_id_seq', 1, false);
        # """
    ]

    #endregion

    #region users 테이블
    users_queries =  [
        """
        CREATE TABLE public.users (
        id text NOT NULL,
        password text,  
        company text,
        department text,
        position text,
        name text,
        access_group_id integer,   
        role_id integer,
        time_stamp bigint,
        logout_time timestamp with time zone,
        is_deleted boolean DEFAULT FALSE,
        login_time timestamp with time zone,
        CONSTRAINT users_pkey PRIMARY KEY (id),
        CONSTRAINT access_group_id FOREIGN KEY (access_group_id) REFERENCES public.content_access_groups(access_group_id) ON DELETE SET NULL,
        CONSTRAINT role_id FOREIGN KEY (role_id) REFERENCES public.roles(role_id) ON DELETE SET NULL NOT VALID 
        );
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_lower_id ON users (LOWER(id)); -- 대소문자 구분 없이 유일한 인덱스 생성
        """
    ]
    #endregion

    #region login_history 테이블
    
    login_history_queries = [
        """
        CREATE TABLE public.login_history (
            id SERIAL NOT NULL PRIMARY KEY,                                         -- 로그인 기록 ID
            user_id text NOT NULL,                                                  -- 사용자 ID
            ip_address text NOT NULL,                                               -- IP 주소
            login_time timestamp with time zone NOT NULL,                           -- 로그인 시간
            logout_time timestamp with time zone,                                   -- 로그아웃 시간
            session_duration interval,                                              -- 세션 지속 시간
            time_stamp bigint,
            CONSTRAINT login_history_pkey PRIMARY KEY (id)
        );
        # """,
        # """ 아카이브는 추후 필요할 때, 추가
        # CREATE TABLE public.login_history_archive (
        #     id integer NOT NULL,                                                   -- 로그인 기록 ID
        #     user_id text NOT NULL,                                                -- 사용자 ID
        #     ip_address text NOT NULL,                                             -- IP 주소
        #     login_time timestamp with time zone NOT NULL,                         -- 로그인 시간
        #     logout_time timestamp with time zone,                                 -- 로그아웃 시간
        #     session_duration interval,                                            -- 세션 지속 시간
        #     time_stamp bigint
        # ) PARTITION BY RANGE (login_time);
        # """
    ]
    
    calculate_session_duration_queries = [
        """
        CREATE OR REPLACE FUNCTION public.calculate_session_duration()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.logout_time IS NOT NULL THEN
                NEW.session_duration = NEW.logout_time - NEW.login_time;
            END IF;
            RETURN NEW;
        END;
        $$;
        """,
        """
        CREATE TRIGGER set_session_duration BEFORE INSERT OR UPDATE ON public.login_history FOR EACH ROW EXECUTE FUNCTION public.calculate_session_duration();
        """
    ]
    
    #endregion
    
    #region content_viewing_history 테이블
    content_viewing_history_queries = [
        """
        CREATE TABLE public.content_viewing_history (
            id SERIAL NOT NULL,
            user_id text,                                   -- 사용자 ID
            file_id integer,                                -- 컨텐츠(파일) ID
            file_type varchar(10) DEFAULT 'page',           -- 파일 타입(페이지, 상세)
            start_time timestamp with time zone NOT NULL,   -- 시작 시간
            end_time timestamp with time zone,              -- 종료 시간
            stay_duration interval,                         -- 체류 시간
            ip_address text NOT NULL,                       -- IP 주소
            time_stamp bigint,
            CONSTRAINT content_viewing_history_pkey PRIMARY KEY (id),
            CONSTRAINT chk_file_type  CHECK (file_type IN ('page','detail'))         -- 파일 타입 체크
        );
        """,
        """
        CREATE INDEX idx_cvh_start_time ON public.content_viewing_history (start_time);
        """,
        """
        CREATE INDEX idx_cvh_user_file ON public.content_viewing_history (user_id, file_id);
        """
    ]
    
    content_viewing_history_archive_queries = """
        CREATE TABLE public.content_viewing_history_archive (
            id integer NOT NULL,
            user_id text,                                   -- 사용자 ID
            file_id integer,                                -- 컨텐츠(파일) ID
            file_type varchar(10) CHECK (file_type IN ('page','detail')), -- 파일 타입(페이지, 상세)
            start_time timestamp with time zone NOT NULL,   -- 시작 시간
            end_time timestamp with time zone,              -- 종료 시간
            stay_duration interval,                         -- 체류 시간
            ip_address text NOT NULL,                       -- IP 주소
            time_stamp bigint
        ) PARTITION BY RANGE (start_time);
    """
    
    content_viewing_history_view_queries = """
        CREATE OR REPLACE VIEW public.content_viewing_history_view AS
        SELECT
            id,
            user_id,
            file_id,
            file_type,
            start_time,
            end_time,
            stay_duration,
            ip_address,
            time_stamp::bigint
        FROM public.content_viewing_history
        UNION ALL
        SELECT
            id,
            user_id,
            file_id,
            file_type,
            start_time,
            end_time,
            stay_duration,
            ip_address,
            time_stamp::bigint
        FROM public.content_viewing_history_archive;
    """
    
    #endregion

    #region Timestamp 업데이트 트리거
    timestamp_update_queries = [     
        """ 
        CREATE FUNCTION public.update_timestamp() RETURNS trigger
            LANGUAGE plpgsql
            AS $$BEGIN
            NEW.time_stamp := EXTRACT(EPOCH FROM NOW() AT TIME ZONE 'UTC');
            RETURN NEW;
        END;$$;
        """,
        """
        CREATE TRIGGER set_timestamp_users BEFORE INSERT OR UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.update_timestamp();
        """,
        """
        CREATE TRIGGER set_timestamp_accessgroupcontents BEFORE INSERT OR UPDATE ON public.access_group_contents FOR EACH ROW EXECUTE FUNCTION public.update_timestamp();
        """,
         """
        CREATE TRIGGER set_timestamp_contentaccessgroups BEFORE INSERT OR UPDATE ON public.content_access_groups FOR EACH ROW EXECUTE FUNCTION public.update_timestamp();
        """,    
        """
        CREATE TRIGGER set_timestamp_roles BEFORE INSERT OR UPDATE ON public.roles FOR EACH ROW EXECUTE FUNCTION public.update_timestamp();
        """,
        """
        CREATE TRIGGER set_timestamp_content_viewing_history BEFORE INSERT OR UPDATE ON public.content_viewing_history FOR EACH ROW EXECUTE FUNCTION public.update_timestamp();
        """,
        """
        CREATE TRIGGER set_timestamp_login_history BEFORE INSERT OR UPDATE ON public.login_history FOR EACH ROW EXECUTE FUNCTION public.update_timestamp();
        """,
        """
        CREATE TRIGGER set_timestamp_learning_completion_history BEFORE INSERT OR UPDATE ON public.learning_completion_history FOR EACH ROW EXECUTE FUNCTION public.update_timestamp();
        """    
    ]
    #endregion
    
    #region login_summary 테이블(로그인 통계 테이블)
    login_summary_queries = [
        # 파티셔닝은 추후 필요할 때 추가 PARTITION BY RANGE (period_value); <-- CREATE TABLE 괄호 뒤에 추가
        """
        CREATE TABLE login_summary_day (
            period_value DATE NOT NULL,         -- '2024-03-28' 등
            company_id INTEGER,
            company TEXT,                       -- 회사명
            department_id INTEGER,
            department TEXT,               -- 부서명
            user_id TEXT,                       -- 개인
            user_name TEXT,                         -- 사용자명
            total_duration INTERVAL NOT NULL DEFAULT '0',            -- 총 접속 시간
            worktime_duration INTERVAL NOT NULL DEFAULT '0',         -- 근무 시간 내 접속
            offhour_duration INTERVAL NOT NULL DEFAULT '0',          -- 근무 시간 외 접속
            internal_count INT NOT NULL DEFAULT 0,                 -- 사내 접속 횟수
            external_count INT NOT NULL DEFAULT 0,                 -- 사외 접속 횟수
            
            -- 가상 컬럼 생성(company, department, user_id에 대한 대체값)
            company_key TEXT GENERATED ALWAYS AS (COALESCE(company, '')) STORED,         -- company_id가 주어지면  COALESCE(company_id, -1)로 대체. -1은 NULL을 대체하기 위한 값으로 실제 칼럼에 사용되지 않는 값.
            department_key TEXT GENERATED ALWAYS AS (COALESCE(department, '')) STORED,   -- department_id가 주어지면 COALESCE(department_id, -1)로 대체. -1은 NULL을 대체하기 위한 값으로 실제 칼럼에 사용되지 않는 값.
            user_id_key TEXT GENERATED ALWAYS AS (COALESCE(user_id, '')) STORED,

            CONSTRAINT login_summary_day_pkey PRIMARY KEY (  -- 기본키 제약 조건
                period_value, 
                company_key,    
                department_key,  
                user_id_key
            )          
        );
        """,      
        """
        CREATE INDEX login_summary_day_unique_user_idx ON login_summary_day (period_value, user_id); -- 조회 시 칼럼 순서 동일해야 함
        """,
        """
        CREATE INDEX login_summary_day_unique_department_idx ON login_summary_day (period_value, company, department); -- department_id가 주어지면 대체하고 company는 제거해도 될 듯
        """,
        """
        CREATE INDEX login_summary_day_unique_company_idx ON login_summary_day (period_value, company);
        """,
        """
        CREATE INDEX login_summary_day_unique_all_idx ON login_summary_day (period_value);
        """,
        """
         CREATE TABLE login_summary_agg (
            period_type TEXT NOT NULL,          -- 'year', 'half', 'quarter'
            period_value TEXT NOT NULL,         -- '2024', '2024H1', '2024Q3' 등
            company_id INTEGER,
            company TEXT,                       -- 회사명 
            department_id INTEGER,
            department TEXT,               -- 부서명
            user_id TEXT,                       -- 개인인 경우
            user_name TEXT,                         -- 사용자명
            total_duration INTERVAL NOT NULL DEFAULT '0',            -- 총 접속 시간
            worktime_duration INTERVAL NOT NULL DEFAULT '0',         -- 근무 시간 내 접속
            offhour_duration INTERVAL NOT NULL DEFAULT '0',          -- 근무 시간 외 접속
            internal_count INT NOT NULL DEFAULT 0,                 -- 사내 접속 횟수
            external_count INT NOT NULL DEFAULT 0,                 -- 사외 접속 횟수   
            
            -- 가상 컬럼 생성(company, department, user_id에 대한 대체값)
            company_key TEXT GENERATED ALWAYS AS (COALESCE(company, '')) STORED,         -- company_id가 주어지면  COALESCE(company_id, -1)로 대체. -1은 NULL을 대체하기 위한 값으로 실제 칼럼에 사용되지 않는 값.
            department_key TEXT GENERATED ALWAYS AS (COALESCE(department, '')) STORED,   -- department_id가 주어지면 COALESCE(department_id, -1)로 대체. -1은 NULL을 대체하기 위한 값으로 실제 칼럼에 사용되지 않는 값.
            user_id_key TEXT GENERATED ALWAYS AS (COALESCE(user_id, '')) STORED,
            
            CONSTRAINT login_summary_agg_pkey PRIMARY KEY (  -- 기본키 제약 조건
                period_type,
                period_value, 
                company_key ,   
                department_key ,
                user_id_key
            ),                              
        );
        """,
        """
        CREATE INDEX login_summary_agg_unique_user_idx ON login_summary_agg (period_type, period_value, user_id);
        """,
        """
        CREATE INDEX login_summary_agg_unique_department_idx ON login_summary_agg (period_type, period_value, company, department);
        """,
        """
        CREATE INDEX login_summary_agg_unique_company_idx ON login_summary_agg (period_type, period_value, company);
        """,
        """
        CREATE INDEX login_summary_agg_unique_all_idx ON login_summary_agg (period_type, period_value);
        """      
    ]
    #endregion
    
    #region leaning_summary 테이블(학습 통계 테이블)
    learning_summary_queries = [
    # 파티셔닝은 추후 필요할 때 추가 PARTITION BY RANGE (stat_date); <-- CREATE TABLE 괄호 뒤에 추가
    """
    CREATE TABLE learning_summary_day (
        stat_date  DATE NOT NULL,         -- '2024-03-28' 등
        company_id INTEGER,
        company TEXT,                       -- 회사명
        department_id INTEGER,
        department TEXT,               -- 부서명
        user_id TEXT,                       -- 개인인 경우
        user_name TEXT,                         -- 사용자명
        channel_id INTEGER,                  -- 채널 ID
        channel_name TEXT,                -- 채널 이름
        total_duration INTERVAL NOT NULL DEFAULT '0',            -- 총 접속 시간
              
        --가상 키(NULL 대체용)
        company_key TEXT GENERATED ALWAYS AS (COALESCE(company, '')) STORED,         -- company_id가 주어지면  COALESCE(company_id, -1)로 대체. -1은 NULL을 대체하기 위한 값으로 실제 칼럼에 사용되지 않는 값.
        department_key TEXT GENERATED ALWAYS AS (COALESCE(department, '')) STORED,   -- department_id가 주어지면 COALESCE(department_id, -1)로 대체. -1은 NULL을 대체하기 위한 값으로 실제 칼럼에 사용되지 않는 값.
        user_id_key TEXT GENERATED ALWAYS AS (COALESCE(user_id, '')) STORED,
        channel_key TEXT GENERATED ALWAYS AS (COALESCE(channel_id, '-1')) STORED,
        
        --제약 조건
        CONSTRAINT pk_learning_summary_day PRIMARY KEY (stat_date , company_key, department_key, user_id_key, channel_key)
    );
    """,
    """
    CREATE INDEX learning_summary_day_user_idx ON learning_summary_day (stat_date, user_id); -- 조회 시 칼럼 순서 동일해야 함
    """,
    """
    CREATE INDEX learning_summary_day_company_idx ON learning_summary_day (stat_date, company);
    """,
    """
    CREATE INDEX learning_summary_day_department_idx ON learning_summary_day (stat_date, company, department); -- department_id가 주어지면 대체하고 company는 제거해도 될 듯
    """,
    """
    CREATE INDEX learning_summary_day_all_idx ON learning_summary_day (stat_date);
    """,
    """
    CREATE TABLE learning_summary_agg (
        period_type TEXT NOT NULL,          -- 'year', 'half', 'quarter'
        period_value TEXT NOT NULL,         -- '2024', '2024H1', '2024Q3' 등
        company_id INTEGER,
        company TEXT,                       -- 회사명
        department_id INTEGER,
        department TEXT,               -- 부서명
        user_id TEXT,                       --개인
        user_name TEXT,                         -- 사용자명
        channel_id INTEGER,                  -- 채널 ID
        channel_name TEXT,                -- 채널 이름
        total_duration INTERVAL NOT NULL DEFAULT '0',            -- 총 접속 시간
                         
        --가상 키(NULL 대체용)
        company_key TEXT GENERATED ALWAYS AS (COALESCE(company, '')) STORED,         -- company_id가 주어지면  COALESCE(company_id, -1)로 대체. -1은 NULL을 대체하기 위한 값으로 실제 칼럼에 사용되지 않는 값.
        department_key TEXT GENERATED ALWAYS AS (COALESCE(department, '')) STORED,   -- department_id가 주어지면 COALESCE(department_id, -1)로 대체. -1은 NULL을 대체하기 위한 값으로 실제 칼럼에 사용되지 않는 값.
        user_id_key TEXT GENERATED ALWAYS AS (COALESCE(user_id, '')) STORED,
        channel_key TEXT GENERATED ALWAYS AS (COALESCE(channel_id, '-1')) STORED,
        
        --제약 조건
        CONSTRAINT pk_learning_summary_agg PRIMARY KEY (period_value , company_key, department_key, user_id_key, channel_key)
    );
    """,
    """
    CREATE INDEX learning_summary_agg_user_idx ON learning_summary_agg (period_value, user_id); -- 조회 시 칼럼 순서 동일해야 함
    """,
    """
    CREATE INDEX learning_summary_agg_company_idx ON learning_summary_agg (period_value, company);
    """,
    """
    CREATE INDEX learning_summary_agg_department_idx ON learning_summary_agg (period_value, company, department); -- department_id가 주어지면 대체하고 company는 제거해도 될 듯
    """,
    """
    CREATE INDEX learning_summary_agg_all_idx ON learning_summary_agg (period_value);
    """
    ]
    
    #endregion
    
    #region content_point_record 테이블(학습 포인트 기록 테이블)
    content_point_record_queries = [
        """
        CREATE TABLE content_point_record (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,       -- 사용자 ID
            file_id INTEGER NOT NULL REFERENCES content_rel_pages(id) ON DELETE CASCADE,    -- 컨텐츠(파일) ID
            point INTEGER NOT NULL CHECK (point >= 1),                          -- 포인트. 최소 1 이상 (insert로만 생성)
            earned_times JSONB NOT NULL DEFAULT '[]'::jsonb,                    -- 포인트 획득 시간 (JSON 배열로 저장)
            file_type varchar(10) DEFAULT 'page',                               -- 파일 타입(페이지, 상세)
            UNIQUE (user_id, file_id),                                          -- 사용자 ID와 파일 ID의 조합은 유일해야 함
            CONSTRAINT chk_file_type CHECK (file_type IN ('page','detail'))     -- 파일 타입 체크
        );
        """
    ]
    #endregion
    
    #region learning_complettion_history 테이블(학습 완료 기록 테이블)
    learning_completion_history_queries = """
        CREATE TABLE learning_completion_history (
            id SERIAL PRIMARY KEY,                -- 학습 완료 기록 ID
            user_id TEXT NOT NULL,               -- 사용자 ID
            page_id INTEGER NOT NULL,            -- 페이지 ID
            completed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),  -- 완료 시간
            total_duration INTERVAL NOT NULL,  -- 총 학습 시간
            time_stamp bigint,
            UNIQUE (user_id, page_id),          -- 사용자 ID와 페이지 ID의 조합은 유일해야 함
        )
    """
    #endregion
    
    #region content_manager 테이블 (컨텐츠 담당 테이블)
    content_manager_queries = """
        CREATE TABLE content_manager (
            id SERIAL PRIMARY KEY,      -- 키
            user_id TEXT NOT NULL,      -- 사번    
            file_id INTEGER,            -- file id
            folder_id INTEGER,          -- folder id
            type VARCHAR(10) NOT NULL CHECK (type IN ('file', 'folder')),   --타입(파일 담당, 폴더 담당)

            CONSTRAINT fk_content_manager_user FOREIGN KEY (user_id) REFERENCES users(id),
            CONSTRAINT fk_content_manager_file FOREIGN KEY (file_id) REFERENCES content_rel_pages(id),
            CONSTRAINT fk_content_manager_folder FOREIGN KEY (folder_id) REFERENCES content_rel_folders(id),

            CONSTRAINT chk_content_manager_file_or_folder CHECK (
                (type = 'file' AND file_id IS NOT NULL AND folder_id IS NULL) OR
                (type = 'folder' AND folder_id IS NOT NULL AND file_id IS NULL)
            )
        );
    """
    #endregion
    
    #region push_messages 테이블 (푸시 메시지 테이블)
    push_messages_queries = [
        """
        CREATE TABLE push_messages (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,       -- 사용자 ID
            title TEXT,                                                         -- 제목   
            message TEXT NOT NULL,                                              -- 메시지 내용
            is_read BOOLEAN DEFAULT FALSE,                                      -- 읽음 여부
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()                   -- 생성 시간
        );
        """,
        """
        CREATE INDEX idx_push_messages_user_read ON push_messages (user_id, is_read);     -- 사용자 ID와 읽음 상태태에 대한 인덱스 생성
        """
    ]
    #endregion 
    
    #region ip_prefixes 테이블 (IP 접두사 테이블)
    
    ip_ranges_queries = """
        CREATE TABLE ip_ranges (
            id SERIAL PRIMARY KEY,
            start_ip TEXT NOT NULL,
            end_ip TEXT NOT NULL,
            label TEXT
        );
    """
    #endregion
   
    #region stay_duration(content_viewing_history) 업데이트 트리거
    stay_duration_update_queries = [
        """
        CREATE FUNCTION calculate_stay_duration() RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.end_time IS NOT NULL THEN
                NEW.stay_duration = NEW.end_time - NEW.start_time;
            END IF;
            RETURN NEW;
        END;
        $$;
        """,
        """
        CREATE TRIGGER set_stay_duration BEFORE INSERT OR UPDATE ON public.content_viewing_history FOR EACH ROW EXECUTE FUNCTION public.calculate_stay_duration();
        """
    ]
    #endregion

    #region 기본 값 추가    
    
    default_insert_queries = [
         # ContentAccessGroups 기본 값 추가
        """
        INSERT INTO public.content_access_groups (group_name) VALUES ('Admin');
        """,
        # Roles 기본 값 추가
        """
        INSERT INTO public.roles (role_name, description) VALUES ('SuperAdmin','{"note": "모든 항목 확인", "user_info": "all", "contents_info": true, "opinion_point": true, "contents_upload": true, "opinion_response": true}');
        """,
        """
        INSERT INTO public.roles (role_name, description) VALUES ('DevAdmin','{"note": "모든 항목 확인", "user_info": "all", "contents_info": true, "opinion_point": false, "contents_upload": true, "opinion_response": false}');
        """,
        """
        INSERT INTO public.roles (role_name, description) VALUES ('ContentAdmin','{"note": "Contents 총괄 관리자", "user_info": "single", "contents_info": true, "opinion_point": true, "contents_upload": false, "opinion_response": true}');
        """,
        """
        INSERT INTO public.roles (role_name, description) VALUES ('ContentEditor','{"note": "Contents 제작 실무자", "user_info": "single", "contents_info": true, "opinion_point": true, "contents_upload": true, "opinion_response": true}');
        """,
        """
        INSERT INTO public.roles (role_name, description) VALUES ('InternalUser','{"note": "일반 사내 사용자", "user_info": "none", "contents_info": false, "opinion_point": false, "contents_upload": false, "opinion_response": false}');
        """,
        """
        INSERT INTO public.roles (role_name, description) VALUES ('ExternalUser','{"note": "일반 사외 사용자", "user_info": "none", "contents_info": false, "opinion_point": false, "contents_upload": false, "opinion_response": false}');
        """
    ]
    
    #endregion

    memos_queries = """
        CREATE TABLE public.memos (
            id text NOT NULL PRIMARY KEY,
            user_id text,
            title text,
            content text,
            path text,
            rel_position_x double precision,
            rel_position_y double precision,
            world_position_x double precision,
            world_position_y double precision,
            world_position_z double precision,
            status integer NOT NULL,
            modified_at timestamp with time zone DEFAULT NOW()
        );
    """

    memo_replies_queries = """
        CREATE TABLE public.memo_replies (
            id SERIAL PRIMARY KEY,
            memo_id text NOT NULL REFERENCES memos(id) ON DELETE CASCADE,
            user_id text NOT NULL REFERENCES users(id),
            content text NOT NULL,
            created_at timestamp with time zone DEFAULT NOW(),
            modified_at timestamp with time zone DEFAULT NOW(),
            is_deleted boolean DEFAULT FALSE
        );
    """
    
        
    queries = [
        content_access_groups_queries, 
        content_access_groups_sequence, 
        access_group_contents_queries, 
        roles_queries, 
        roles_sequence, 
        users_queries, 
        login_history_queries,
        calculate_session_duration_queries,
        content_viewing_history_queries,
        #content_viewing_history_archive_queries,  아카이브는 추후 필요할 때 추가
        #content_viewing_history_view_queries,
        timestamp_update_queries, 
        stay_duration_update_queries,
        default_insert_queries,
        memos_queries,
        memo_replies_queries,
        login_summary_queries,
        learning_summary_queries,
        content_point_record_queries,
        content_manager_queries,
        push_messages_queries,
        learning_completion_history_queries,
        ip_ranges_queries
        ]

    for query in queries:
        if isinstance(query, list):
            for q in query:
                cursor.execute(q)
        else:
            cursor.execute(query)

    connection.commit()
except Exception as e:
    print(f"Error: {e}")
    connection.rollback()
finally:
    cursor.close()
    connection.close()
    
