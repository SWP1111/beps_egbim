import datetime
import logging
import traceback
import log_config
from flask import Blueprint, jsonify, request
from extensions import db
from flask_jwt_extended import jwt_required, get_jwt_identity
from blueprints.leaning.leaning_routes import api_leaning_bp
from config import Config
from models import (Users, ContentViewingHistory, ContentPointRecord, ContentRelPages, LearningCompletionHistory
                    , ContentManager, ContentRelFolders, ContentRelChannels)
from sqlalchemy import text, func
from . import api_leaning_bp

#🔹 GET /learning_time_by_date_range API 주어진 기간에 대한 전체 평균과 특정 사용자 학습시간 조회
@api_leaning_bp.route('/learning_time_by_date_range', methods=['GET'])
@jwt_required(locations=['headers', 'cookies'])
def get_learning_time_of_week():
    """
    주어진 기간에 대한 전체 평균과 특정 사용자 학습시간 조회
    Returns:
        JSON: 전체 학습자 일별 평균 학습시간 및 특정 사용자 일별 학습시간
    """
    try:
        user_id = get_jwt_identity()
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            return jsonify({"error": "Please provide start_date and end_date"}), 400
        
        try:
            start_date_obj = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
        
        # 로컬 시간대를 UTC로 변환
        local_tz = datetime.datetime.now().astimezone().tzinfo
        local_tz_name = local_tz.tzname(None)
        if local_tz_name == 'KST':
            local_tz_name = 'Asia/Seoul'
            
        utc_start_date = datetime.datetime.combine(start_date_obj, datetime.time.min, tzinfo=local_tz).astimezone(datetime.timezone.utc)
        utc_end_date = datetime.datetime.combine(end_date_obj, datetime.time.max, tzinfo=local_tz).astimezone(datetime.timezone.utc)
        
        logging.debug(f"Request range: {start_date} ~ {end_date}")
        logging.debug(f"UTC range: {utc_start_date} ~ {utc_end_date}")
        logging.debug(f"Local timezone: {local_tz}")      
        
        # 전체 학습자 일별 평균 학습시간 조회 (전체 사용자 기준 평균)
        all_users_query = text("""
            WITH all_users AS (
                SELECT COUNT(*) as total_user_count FROM users WHERE is_deleted = false
            ),
            daily_learning AS (
                SELECT 
                    DATE(start_time AT TIME ZONE :local_tz_name) as date,
                    user_id,
                    SUM(EXTRACT(EPOCH FROM stay_duration)) as daily_seconds
                FROM content_viewing_history
                WHERE start_time >= :utc_start_date 
                    AND start_time <= :utc_end_date
                    AND stay_duration IS NOT NULL
                GROUP BY DATE(start_time AT TIME ZONE :local_tz_name), user_id
            )
            SELECT 
                dl.date,
                SUM(dl.daily_seconds) / au.total_user_count as avg_duration_seconds,
                au.total_user_count,
                COUNT(dl.user_id) as active_user_count
            FROM daily_learning dl
            CROSS JOIN all_users au
            GROUP BY dl.date, au.total_user_count
            ORDER BY dl.date
        """)
        
        all_users_result = db.session.execute(all_users_query, {
            'utc_start_date': utc_start_date,
            'utc_end_date': utc_end_date,
            'local_tz_name': local_tz_name
        })
        
        # 특정 사용자 일별 학습시간 조회 (한국 시간 기준)
        user_query = text("""
            SELECT 
                DATE(start_time AT TIME ZONE :local_tz_name) as date,
                SUM(EXTRACT(EPOCH FROM stay_duration)) as total_duration_seconds
            FROM content_viewing_history
            WHERE user_id = :user_id
                AND start_time >= :utc_start_date 
                AND start_time <= :utc_end_date
                AND stay_duration IS NOT NULL
            GROUP BY DATE(start_time AT TIME ZONE :local_tz_name)
            ORDER BY date
        """)
        
        logging.debug(f"User query parameters: user_id={user_id}, utc_start_date={utc_start_date}, utc_end_date={utc_end_date}")
        
        user_result = db.session.execute(user_query, {
            'user_id': user_id,
            'utc_start_date': utc_start_date,
            'utc_end_date': utc_end_date,
            'local_tz_name': local_tz_name
        })
        
        # 전체 학습자 평균 데이터 처리
        all_users_data = []
        for row in all_users_result:
            date_str = row[0].strftime('%Y-%m-%d')
            avg_minutes = round(float(row[1]) / 60, 2) if row[1] else 0
            total_user_count = row[2] if row[2] else 0
            active_user_count = row[3] if row[3] else 0
            all_users_data.append({
                'date': date_str,
                'avg_duration_minutes': avg_minutes
            })
            logging.debug(f"All users data - Date: {date_str}, Avg minutes: {avg_minutes}, Total users: {total_user_count}, Active users: {active_user_count}")
        
        # 특정 사용자 데이터 처리
        user_data = []
        user_record_count = 0
        for row in user_result:
            user_record_count += 1
            date_str = row[0].strftime('%Y-%m-%d')
            duration_minutes = round(float(row[1]) / 60, 2) if row[1] else 0
            user_data.append({
                'date': date_str,
                'total_duration_minutes': duration_minutes
            })
            logging.debug(f"User data - Date: {date_str}, Duration minutes: {duration_minutes}")
        
        logging.debug(f"User query returned {user_record_count} records")
        if user_record_count == 0:
            logging.debug(f"No user data found for user_id: {user_id}")
            # 사용자 데이터가 없는 경우 디버그를 위해 사용자별 원시 데이터 확인
            user_debug_query = text("""
                SELECT COUNT(*) as count
                FROM content_viewing_history
                WHERE user_id = :user_id
                    AND start_time >= :utc_start_date 
                    AND start_time <= :utc_end_date
                    AND stay_duration IS NOT NULL
            """)
            user_debug_result = db.session.execute(user_debug_query, {
                'user_id': user_id,
                'utc_start_date': utc_start_date,
                'utc_end_date': utc_end_date
            })
            user_debug_count = user_debug_result.fetchone()[0]
            logging.debug(f"Raw user data count for debugging: {user_debug_count}")
        
        logging.debug(f"Final all_users_data count: {len(all_users_data)}")
        logging.debug(f"Final user_data count: {len(user_data)}")
        
        data = {
            'all_users_daily_average': all_users_data,
            'user_daily_total': user_data,
            'timezone': local_tz_name,
        }
        
        return jsonify(data), 200
    except Exception as e:
        logging.error(f"Error in get_learning_time_of_week: {str(e)}, {traceback.format_exc()}")
        return jsonify({"error": "Internal server error"}), 500 


#🔹 GET /continuous_learning_days API 사용자의 연속 학습일 조회
@api_leaning_bp.route('/continuous_learning_days', methods=['GET'])
@jwt_required(locations=['headers', 'cookies'])
def get_continuous_learning_days():
    """
    사용자의 연속 학습일 조회
    Returns:
        JSON: 특정 날짜 기준으로 연속 학습일 수
    """
    try:
        user_id = get_jwt_identity()
        reference_date = request.args.get('reference_date')
        
        if not reference_date:
            return jsonify({"error": "Please provide reference_date"}), 400
        
        try:
            reference_date_obj = datetime.datetime.strptime(reference_date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
        
        # 로컬 시간대 설정
        local_tz = datetime.datetime.now().astimezone().tzinfo
        local_tz_name = local_tz.tzname(None)
        if local_tz_name == 'KST':
            local_tz_name = 'Asia/Seoul'
        
        logging.debug(f"Calculating continuous learning days for user: {user_id}, reference_date: {reference_date}")
        
        # 기준 날짜부터 과거로 거슬러 올라가면서 연속 학습일 계산
        query = text("""
            WITH learning_dates AS (
                SELECT DISTINCT DATE(start_time AT TIME ZONE :local_tz_name) as learning_date
                FROM content_viewing_history
                WHERE user_id = :user_id
                    AND stay_duration IS NOT NULL
                    AND EXTRACT(EPOCH FROM stay_duration) > 0
                    AND DATE(start_time AT TIME ZONE :local_tz_name) <= :reference_date
                ORDER BY learning_date DESC
            ),
            consecutive_check AS (
                SELECT 
                    learning_date,
                    ROW_NUMBER() OVER (ORDER BY learning_date DESC) as row_num,
                    :reference_date - learning_date as days_diff
                FROM learning_dates
            )
            SELECT COUNT(*) as continuous_days
            FROM consecutive_check
            WHERE days_diff = row_num - 1
                AND learning_date <= :reference_date
        """)
        
        params = {
            'user_id': user_id,
            'reference_date': reference_date_obj,  # date 객체 전달
            'local_tz_name': local_tz_name
        }
        
        logging.debug(f"Executing query: {query}")
        logging.debug(f"Query parameters: {params}")
        
        result = db.session.execute(query, params)
        
        row = result.fetchone()
        continuous_days = row[0] if row and row[0] else 0
        
        logging.debug(f"Continuous learning days calculated: {continuous_days}")
        
        return jsonify({
            'user_id': user_id,
            'reference_date': reference_date,
            'continuous_days': continuous_days,
            'timezone': local_tz_name
        }), 200
        
    except Exception as e:
        logging.error(f"Error in get_continuous_learning_days: {str(e)}, {traceback.format_exc()}")
        return jsonify({"error": "Internal server error"}), 500
    

#🔹 GET /get_learning_time_date API 주어진 날짜에 대한 사용자의 학습 시간 조회
@api_leaning_bp.route('/get_learning_time_date', methods=['GET'])
@jwt_required(locations=['headers', 'cookies'])
def get_learning_time():
    """
    주어진 날짜에 대한 사용자의 학습 시간 조회
    Returns:
        JSON: 사용자의 총 학습 시간
    """
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401
        
        date = request.args.get('date')
        if not date:
            return jsonify({"error": "Please provide a date"}), 400
        
        try:
            date_obj = datetime.datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({"error": "Invalid date format. Please use YYYY-MM-DD."}), 400

        local_tz = datetime.datetime.now().astimezone().tzinfo
        local_tz_name = local_tz.tzname(None)
        if local_tz_name == 'KST':
            local_tz_name = 'Asia/Seoul'
            
        utc_start = datetime.datetime.combine(date_obj, datetime.time.min, tzinfo=local_tz).astimezone(datetime.timezone.utc)
        utc_end = datetime.datetime.combine(date_obj, datetime.time.max, tzinfo=local_tz).astimezone(datetime.timezone.utc)
        
        # 전체 학습자 일별 평균 학습시간 조회 (전체 사용자 기준 평균)
        all_users_query = text("""
            WITH all_users AS (
                SELECT COUNT(*) as total_user_count FROM users WHERE is_deleted = false
            ),
            daily_learning AS (
                SELECT 
                    DATE(start_time AT TIME ZONE :local_tz_name) as date,
                    user_id,
                    SUM(EXTRACT(EPOCH FROM stay_duration)) as daily_seconds
                FROM content_viewing_history
                WHERE start_time >= :utc_start_date 
                    AND start_time <= :utc_end_date
                    AND stay_duration IS NOT NULL
                GROUP BY DATE(start_time AT TIME ZONE :local_tz_name), user_id
            )
            SELECT 
                dl.date,
                SUM(dl.daily_seconds) / au.total_user_count as avg_duration_seconds,
                au.total_user_count,
                COUNT(dl.user_id) as active_user_count
            FROM daily_learning dl
            CROSS JOIN all_users au
            GROUP BY dl.date, au.total_user_count
            ORDER BY dl.date
        """)
        
        result = db.session.execute(all_users_query, {
            'utc_start_date': utc_start,
            'utc_end_date': utc_end,
            'local_tz_name': local_tz_name
        })
        row = result.fetchone()
        
        # 전체 학습자 평균 데이터 처리
        all_users_avg_learning_time_minutes = 0
        if row:
            avg_minutes = round(float(row[1]) / 60, 2) if row[1] else 0
            all_users_avg_learning_time_minutes = avg_minutes
            
        # 특정 사용자 일별 학습시간 조회
        query = text("""
            SELECT 
                SUM(EXTRACT(EPOCH FROM stay_duration)) as total_seconds
            FROM content_viewing_history
            WHERE user_id = :user_id
                AND stay_duration IS NOT NULL
                AND start_time >= :utc_start
                AND start_time <= :utc_end
        """)

        result = db.session.execute(query, {'user_id': user_id, 'utc_start': utc_start, 'utc_end': utc_end})
        row = result.fetchone()
        
        total_seconds = row[0] if row and row[0] else 0
        total_minutes = float(round(total_seconds / 60, 2))

        return jsonify({
            'user_id': user_id,
            'total_learning_time_minutes': total_minutes,
            'all_users_avg_learning_time_minutes': all_users_avg_learning_time_minutes,
            'timezone': local_tz_name
        }), 200
    except Exception as e:
        logging.error(f"Error in get_learning_time: {str(e)}, {traceback.format_exc()}")
        return jsonify({"error": "Internal server error"}), 500
    

#🔹 GET /leaning/category_progress API 카테고리별 학습 진행률 조회(시간)      
@api_leaning_bp.route('/category_progress', methods=['GET'])
@jwt_required(locations=['headers','cookies'])  # 🔹 JWT 검증을 먼저 수행
def category_progress():
    from services.leaning_summary_service import get_folder_progress
    try:
        filter_type = request.args.get('filter_type', 'all')
        filter_value = request.args.get('filter_value')
        period_type = request.args.get('period_type', 'year')
        period_value = request.args.get('period_value')
        
        if not period_type or not period_value:
            return jsonify({'error': 'Please provide scope, period_type, and period_value'}), 400
        
        params = {
            'filter_type': filter_type,
            'filter_value': filter_value,
            'period_type': period_type,
            'period_value': period_value
        }
        
        folder_duration_map = get_folder_progress(params)
        
        if not folder_duration_map:
            return jsonify({'error': 'No data found'}), 404
        
        total_duration = sum((duration for _, duration in folder_duration_map.values()), datetime.timedelta(0))
        total_seconds = total_duration.total_seconds()
        if total_seconds == 0:
            total_seconds = 1  # Avoid division by zero
        
        result = []
        for channel_id, (channel_name, duration) in folder_duration_map.items():
            duration_seconds = duration.total_seconds() if duration else 0
            percentage = round(duration_seconds / total_seconds * 100, 1)
            hour = duration_seconds // 3600
            minute = (duration_seconds % 3600) // 60
            second = duration_seconds % 60
            result.append({
                'channel_id': channel_id,
                'channel_name': channel_name,
                'duration': f"{int(hour):02}:{int(minute):02}:{int(second):02}",
                'percentage': percentage
            })
            
        return jsonify({'progress': result}), 200  # 200: OK
    
    except Exception as e:
        logging.error(f"[category_progress] error: {str(e)}, {traceback.format_exc()}")
        return jsonify({'[category_progress] error': str(e)}), 500
    

# 🔹 GET /leaning/get_learning_rate_per_category API 카테고리별 학습률 조회(진도율)
@api_leaning_bp.route('/get_learning_rate_per_category', methods=['GET'])
@jwt_required(locations=['headers','cookies'])  # 🔹 JWT 검증을 먼저 수행
def get_learning_rate_per_category():
    try:
        type = request.args.get('type', 'user')
        user_id = request.args.get('user_id')
        
        if type not in ['user', 'all']:
            return jsonify({'error': 'Invalid type. Must be one of: user, all'}), 400
        
        if type == 'user' and not user_id:
            user_id = get_jwt_identity()

        total_pages = db.session.query(
            ContentRelChannels.id.label('channel_id'),
            ContentRelChannels.name.label('channel_name'),
            func.count(ContentRelPages.id).label('total_pages')
        )\
        .join(ContentRelFolders, ContentRelFolders.channel_id == ContentRelChannels.id)\
        .join(ContentRelPages, ContentRelPages.folder_id == ContentRelFolders.id)\
        .group_by(ContentRelChannels.id, ContentRelChannels.name)\
        .all()

        total_pages_dict = {row.channel_id: {'channel_name': row.channel_name, 'total_pages': row.total_pages} for row in total_pages}

        params = {
            "completed_threshold": f"{Config.LEARNING_COMPLETED_MINUTES * 60} seconds"  # 초 단위로 변환
        }
                
        if type == 'user':
            params['user_id'] = user_id
            sql_template = """
                WITH all_channels AS (
                    SELECT DISTINCT ch.id AS channel_id
                    FROM content_rel_channels ch
                    WHERE ch.is_deleted = false
                ),
                completed AS (
                    SELECT l.user_id, ch.id AS channel_id, COUNT(DISTINCT l.page_id) AS completed_pages
                    FROM learning_completion_history l
                    JOIN content_rel_pages p ON l.page_id = p.id
                    JOIN content_rel_folders f ON p.folder_id = f.id
                    JOIN content_rel_channels ch ON f.channel_id = ch.id
                    WHERE l.total_duration >= interval :completed_threshold
                    AND l.user_id = :user_id
                    GROUP BY l.user_id, ch.id
                ),
                aggregated AS (
                    SELECT ac.channel_id, 
                           COALESCE(c.completed_pages, 0) AS completed_pages
                    FROM all_channels ac
                    LEFT JOIN completed c ON ac.channel_id = c.channel_id
                )
                SELECT channel_id, completed_pages
                FROM aggregated
            """
        else:
            # 전체 사용자 기준 평균 계산 (학습 기록이 없는 사용자도 포함)
            sql_template = """
                WITH all_users AS (
                    SELECT u.id as user_id
                    FROM users u
                    WHERE u.is_deleted = false
                ),
                all_channels AS (
                    SELECT DISTINCT ch.id AS channel_id
                    FROM content_rel_channels ch
                    WHERE ch.is_deleted = false
                ),
                user_channel_combinations AS (
                    SELECT au.user_id, ac.channel_id
                    FROM all_users au
                    CROSS JOIN all_channels ac
                ),
                completed AS (
                    SELECT l.user_id, ch.id AS channel_id, COUNT(DISTINCT l.page_id) AS completed_pages
                    FROM learning_completion_history l
                    JOIN content_rel_pages p ON l.page_id = p.id
                    JOIN content_rel_folders f ON p.folder_id = f.id
                    JOIN content_rel_channels ch ON f.channel_id = ch.id
                    WHERE l.total_duration >= interval :completed_threshold
                    GROUP BY l.user_id, ch.id
                ),
                user_completed AS (
                    SELECT ucc.user_id, ucc.channel_id, COALESCE(c.completed_pages, 0) AS completed_pages
                    FROM user_channel_combinations ucc
                    LEFT JOIN completed c ON ucc.user_id = c.user_id AND ucc.channel_id = c.channel_id
                ),
                aggregated AS (
                    SELECT channel_id, 
                           AVG(completed_pages) AS completed_pages
                    FROM user_completed
                    GROUP BY channel_id
                )
                SELECT channel_id, completed_pages
                FROM aggregated
            """
            
        sql = text(sql_template)        
        rows = db.session.execute(sql, params).fetchall()

        result = []
        for row in rows:
            info = total_pages_dict.get(row.channel_id)
            if not info:
                continue

            completed = row.completed_pages or 0
            total = info['total_pages'] or 0
            rate = round(completed / total * 100, 2) if total > 0 else 0
                
            result.append({
                "channel_id": row.channel_id,
                "channel_name": info['channel_name'],
                "completed_pages": completed,
                "total_pages": total,
                "progress_rate": rate
            })

        return jsonify(result), 200  # 200: OK
    except Exception as e:
        logging.error(f"[get_learning_rate_per_category] error: {str(e)}, {traceback.format_exc()}")
        return jsonify({'[get_learning_rate_per_category] error': str(e)}), 500