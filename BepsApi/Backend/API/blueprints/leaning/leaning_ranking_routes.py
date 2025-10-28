import datetime
import logging
import traceback
import log_config
from flask import Blueprint, jsonify, request
from extensions import db
from flask_jwt_extended import jwt_required, get_jwt_identity
from blueprints.leaning.leaning_routes import api_leaning_bp
from config import Config
from models import (Users, ContentViewingHistory, ContentPointRecord, ContentRelPages, LearningCompletionHistory, Assignees
                    , ContentManager, ContentRelFolders, ContentRelChannels)
from sqlalchemy import func, text
from sqlalchemy.orm import aliased
from . import api_leaning_bp

# 🔹 GET /leaning/point/rank API 포인트 랭킹 조회
@api_leaning_bp.route('/point/rank', methods=['GET'])
@jwt_required(locations=['headers','cookies'])  # 🔹 JWT 검증을 먼저 수행
def point_rank():
    import services.user_summary_service as user_summary_service
    try:
        period_type = request.args.get('period_type', 'year')
        period_value = request.args.get('period_value')
        filter_type = request.args.get('filter_type', 'all')
        
        if period_type != 'year' and period_type is None:
            return jsonify({'error': 'Please provide period_type'}), 400    # 400: Bad Request
        
        if filter_type in ['all','company', 'department'] is False:
            return jsonify({'error': 'Please provide filter_type'}), 400    # 400: Bad Request
        
        start_date, end_date = user_summary_service.get_period_value(period_type, period_value)
        local_tz = datetime.datetime.now().astimezone().tzinfo
        utc_start_date = datetime.datetime.combine(start_date, datetime.time.min, tzinfo=local_tz).astimezone(datetime.timezone.utc)
        utc_end_date = datetime.datetime.combine(end_date, datetime.time.max, tzinfo=local_tz).astimezone(datetime.timezone.utc)
        
        filters = {'start_date': utc_start_date, 'end_date': utc_end_date}
        
        if filter_type == 'all':
            select_field = 'u.id, COALESCE(u.name,\'[삭제된 사용자]\') AS name'
            group_by_field = 'u.id, u.name'
        elif filter_type == 'company':
            select_field = 'u.company'
            group_by_field = 'u.company'
        elif filter_type == 'department':
            select_field = 'u.company, u.department'
            group_by_field = 'u.company, u.department'
        else:
            return jsonify({'error': 'Invalid filter_type'}), 400    # 400: Bad Request
        
        rank_sql = f"""
            SELECT {select_field}, COALESCE(SUM(
                CASE
                    WHEN earned_time IS NOT NULL
                            AND earned_time::timestamp BETWEEN :start_date AND :end_date
                    THEN cpr.point
                    ELSE 0
                END), 0) AS total_points
            FROM users u
            LEFT JOIN content_point_record cpr ON u.id = cpr.user_id
            LEFT JOIN LATERAL jsonb_array_elements_text(cpr.earned_times) AS earned_time ON TRUE
            WHERE u.is_deleted = FALSE
            GROUP BY {group_by_field}
        """
        
        all_rows = db.session.execute(text(rank_sql), filters).mappings().all()
        sorted_rows = sorted(all_rows, key=lambda x: x['total_points'], reverse=True)   
        
         # 상위, 하위 점수 찾기
        top_score = sorted_rows[0]['total_points']
        bottom_score = sorted_rows[-1]['total_points']
        
        # 상위/하위 동점자 모두 추출
        top_list = [dict(row) for row in sorted_rows if row['total_points'] == top_score]
        bottom_list = [dict(row) for row in sorted_rows if row['total_points'] == bottom_score]
        
        return jsonify({
            'top': top_list,
            'bottom': bottom_list,
        }), 200  # 200: OK
        
    except Exception as e:
        return jsonify({'[point/rank] error': str(e)}), 500
    
        
# 🔹 GET /leaning/top_viewd_pages API 상위 조회 페이지 조회
@api_leaning_bp.route('/top_viewed_pages', methods=['GET'])
@jwt_required(locations=['headers','cookies'])  # 🔹 JWT 검증을 먼저 수행   
def get_top_viewd_pages():
    from services.user_summary_service import get_period_value
    try:
        filter_type = request.args.get('filter_type', 'all')
        filter_value = request.args.get('filter_value')
        period_type = request.args.get('period_type', 'year')
        period_value = request.args.get('period_value')
        
        if not period_type or not period_value:
            return jsonify({'error': 'Please provide scope, period_type, and period_value'}), 400
        
        start_dt, end_dt = get_period_value(period_type, period_value)
        local_tz = datetime.datetime.now().astimezone().tzinfo
        utc_start_date = datetime.datetime.combine(start_dt, datetime.time.min, tzinfo=local_tz).astimezone(datetime.timezone.utc)
        utc_end_date = datetime.datetime.combine(end_dt, datetime.time.max, tzinfo=local_tz).astimezone(datetime.timezone.utc)

        query = db.session.query(
            ContentViewingHistory.file_id,
            func.coalesce(ContentRelPages.name, '[삭제된 파일]').label('file_name'),
            func.coalesce(ContentRelFolders.name, '[삭제된 폴더]').label('folder_name'),
            func.coalesce(ContentRelChannels.name, '[삭제된 채널]').label('channel_name'),
            ContentRelPages.updated_at,
            func.count().label('view_count')
        )
        
        if filter_type in ('company','department','user'):
            query = query.join(Users, ContentViewingHistory.user_id == Users.id)
            query = query.filter(Users.is_deleted == False)  # 사용자 삭제 여부 필터링
            
        query = query.outerjoin(
            ContentRelPages, ContentViewingHistory.file_id == ContentRelPages.id
            ).outerjoin(
                ContentRelFolders, ContentRelPages.folder_id == ContentRelFolders.id
            ).outerjoin(
                ContentRelChannels, ContentRelFolders.channel_id == ContentRelChannels.id
            ).filter(
                ContentViewingHistory.start_time >= utc_start_date,
                ContentViewingHistory.start_time <= utc_end_date
            )     
        
        if filter_type == 'company' and filter_value:
            query = query.filter(Users.company == filter_value)
        elif filter_type == 'department' and filter_value:
            parts = filter_value.split('||', 1)
            if len(parts) == 2:
                query = query.filter(Users.company == parts[0], Users.department == parts[1])
            else:
                query = query.filter(Users.company == filter_value)
        elif filter_type == 'user' and filter_value:
            query = query.filter(Users.id == filter_value)

        query = query.group_by(ContentViewingHistory.file_id, ContentRelPages.name, ContentRelFolders.name, ContentRelChannels.name, ContentRelPages.updated_at).order_by(func.count().desc())
        query = query.limit(5)  # 🔹 상위 5개 조회
        
        rows = query.all()
        
        return jsonify({
            'top_viewd_pages': [
                {
                    'file_id': row.file_id,
                    'file_name': row.file_name,
                    'folder_name': row.folder_name,
                    'channel_name': row.channel_name,
                    'view_count': row.view_count,
                    'updated_at': row.updated_at.isoformat() if row.updated_at else None
                } for row in rows
            ]
        }), 200  # 200: OK
        
    except Exception as e:
        logging.error(f"[get_top_viewd_pages] error: {str(e)}, {traceback.format_exc()}")
        return jsonify({'[get_top_viewd_pages] error': str(e)}), 500
       

# 🔹 GET /leaning/rank-update-contents API 최근 업데이트된 콘텐츠 랭킹 조회
@api_leaning_bp.route('/rank-update-contents', methods=['GET'])
@jwt_required(locations=['headers','cookies'])  # 🔹 JWT 검증을 먼저 수행
def rank_update_contents():
    try:

        cm = aliased(ContentManager)
        u = aliased(Users)
        a = aliased(Assignees)
        
        top_rows = db.session.query(
                ContentRelPages.id,
                ContentRelPages.name,
                ContentRelPages.updated_at,
                u.id.label('manager_id'),
                u.name.label('manager_name')
            ).outerjoin(
                cm, (cm.type == 'file') & (cm.file_id == ContentRelPages.id)
            ).outerjoin(
                a, a.id == cm.assignee_id
            ).outerjoin(
                u, u.id == a.user_id
            ).filter(
                ContentRelPages.is_deleted == False
            ).order_by(
                ContentRelPages.updated_at.desc()
            ).limit(5).all()  # 상위 5개만 조회
            
        bottom_rows = db.session.query(
                ContentRelPages.id,
                ContentRelPages.name,
                ContentRelPages.updated_at,
                a.user_id.label('manager_id'),
                u.name.label('manager_name')
            ).outerjoin(
                cm, (cm.type == 'file') & (cm.file_id == ContentRelPages.id)
            ).outerjoin(
                a, a.id == cm.assignee_id
            ).outerjoin(
                u, u.id == a.user_id
            ).filter(
                ContentRelPages.is_deleted == False
            ).order_by(
                ContentRelPages.updated_at.asc()
            ).limit(5).all()  # 하위 5개만 조회

        return jsonify({
            'top': [
                {
                    'id': row.id,
                    'name': row.name,
                    'updated_at': row.updated_at.isoformat() if row.updated_at else None,
                    'manager_id': row.manager_id,
                    'manager_name': row.manager_name
                } for row in top_rows
            ],
            'bottom': [
                {
                    'id': row.id,
                    'name': row.name,
                    'updated_at': row.updated_at.isoformat() if row.updated_at else None,
                    'manager_id': row.manager_id,
                    'manager_name': row.manager_name    
                } for row in bottom_rows
            ]
        }), 200  # 200: OK
        
    except Exception as e:
        logging.error(f"[rank_update_contents] error: {str(e)}, {traceback.format_exc()}")
        return jsonify({'[rank_update_contents] error': str(e)}), 500


# 🔹 GET /leaning/get_updated_contents API 최근 업데이트 된 콘텐츠 조회
@api_leaning_bp.route('/get_updated_contents', methods=['GET'])
@jwt_required(locations=['headers', 'cookies'])
def get_updated_contents():
    """최근 업데이트 된 콘텐츠 조회"""
    try:
        user_id = get_jwt_identity()
        searchDays = request.args.get('days', 14, type=int)
        if searchDays <= 0:
            return jsonify({"error": "Invalid number of days"}), 400
        
        today = datetime.datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        utc_today = today.astimezone(datetime.timezone.utc)
        start_date = utc_today - datetime.timedelta(days=searchDays)
        
        # 최근 업데이트된 콘텐츠와 사용자의 학습 상태, 담당자 정보를 함께 조회
        query = text("""
            SELECT 
                p.id,
                p.name,
                p.updated_at,
                CASE 
                    WHEN cvh.latest_start_time IS NOT NULL AND cvh.latest_start_time > p.updated_at 
                    THEN true 
                    ELSE false 
                END as viewed_after_update,
                u.name as manager_name
            FROM content_rel_pages p
            LEFT JOIN (
                SELECT 
                    file_id,
                    MAX(start_time) as latest_start_time
                FROM content_viewing_history
                WHERE user_id = :user_id 
                    AND file_type = 'page'
                GROUP BY file_id
            ) cvh ON p.id = cvh.file_id
            LEFT JOIN content_manager cm ON p.id = cm.file_id AND cm.type = 'file'
            LEFT JOIN assignees a ON a.id = cm.assignee_id
            LEFT JOIN users u ON a.user_id = u.id AND u.is_deleted = false
            WHERE p.updated_at >= :start_date
                AND p.is_deleted = false
            ORDER BY p.updated_at DESC
        """)
        
        result = db.session.execute(query, {
            'user_id': user_id,
            'start_date': start_date
        })
        
        contents = []
        for row in result:
            content_dict = {
                'id': row[0],
                'name': row[1],
                'updated_at': row[2].isoformat() if row[2] else None,
                'viewed_after_update': row[3],
                'manager_name': row[4]  # 담당자 이름 (없으면 None)
            }
            contents.append(content_dict)
        
        return jsonify({
            "contents": contents
        }), 200
    except Exception as e:
        logging.error(f"Error in get_updated_contents: {str(e)}, {traceback.format_exc()}")
        return jsonify({"error": "Internal server error"}), 500
    

@api_leaning_bp.route('/my_learning_rank', methods=['GET'])
@jwt_required(locations=['headers', 'cookies'])
def get_my_learning_rank():
    """
    사용자 학습 랭킹 조회
    Returns:
        JSON: 사용자 학습 랭킹
    """
    try:
        user_id = get_jwt_identity()
        
        min_seconds = Config.LEARNING_COMPLETED_MINUTES * 60  # Convert minutes to seconds
        
        query = text("""
                    WITH user_completed AS (
                        SELECT lch.user_id, COUNT(*) AS completed_pages
                        FROM learning_completion_history lch
                        JOIN users u ON u.id = lch.user_id
                        WHERE EXTRACT(EPOCH FROM lch.total_duration) >= :min_seconds
                        AND u.is_deleted = FALSE
                        GROUP BY lch.user_id
                    )
                    SELECT COUNT(*) + 1 AS rank
                    FROM user_completed
                    WHERE completed_pages > (
                        SELECT COUNT(*)
                        FROM learning_completion_history
                        WHERE user_id = :user_id AND EXTRACT(EPOCH FROM total_duration) >= :min_seconds
                    )
                    """)
        
        result = db.session.execute(query, {'user_id': user_id, 'min_seconds': min_seconds})
        row = result.fetchone()
        return jsonify({'rank': row[0] if row else 0}), 200
    except Exception as e:
        logging.error(f"Error in get_my_learning_rank: {str(e)}, {traceback.format_exc()}")
        return jsonify({"error": "Internal server error"}), 500
