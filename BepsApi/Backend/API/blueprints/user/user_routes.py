import logging
import os
import re
import log_config
import decryption
from flask import Blueprint, jsonify, request, make_response
from flask_jwt_extended import create_access_token, decode_token, get_csrf_token, jwt_required, get_jwt_identity, verify_jwt_in_request, get_jwt
import datetime
from datetime import timezone
from extensions import db
from models import Users, Roles, ContentAccessGroups, LoginHistory, loginSummaryDay, loginSummaryAgg, IpRange, Assignees
from sqlalchemy.exc import OperationalError
from sqlalchemy.sql import text
import requests
from collections import defaultdict
from urllib.parse import unquote
from sqlalchemy import cast, exists, func, or_
from sqlalchemy.dialects.postgresql import INET
import services.user_summary_service as summary_service
import traceback
from sqlalchemy import case
import json
from utils.user_query_utils import get_user_ids_by_scope
from utils.swagger_loader import get_swag_from
from . import api_user_bp, yaml_folder

# 유효한 값인지 확인하는 함수, key가 data에 존재하고 '@' 또는 -1이 아닌 값이면 유효한 값으로 판단
def is_valid(key, data):
    return key in data and data[key] not in ('@', -1)

#DB /user/db_status API 연결 상태 확인
@api_user_bp.route('/db_status', methods=['GET'])
@get_swag_from(yaml_folder, 'db_status.yaml')
def check_db_status():
    """
    DB 연결 상태 확인 API
    """
    try:
        logging.info(f"GET /db_status {db.engine.url}")
        db.session.execute(text('SELECT 1'))
        return jsonify({'status': 'OK'})
    except OperationalError as e:
        return jsonify({'error': str(e)}), 500


# GET /user/user_info API Users 테이블 Row 조회 API (사용자 정보 조회)_인증된 사용자용
@api_user_bp.route('/user_info', methods=['GET'])
@jwt_required(locations=['headers','cookies'])  # JWT 검증을 먼저 수행
@get_swag_from(yaml_folder, 'user_info.yaml')
def get_user_info():
    try:
        user_id = request.args.get('id').lower()
        if user_id is None:
            return jsonify({'error': 'Please provide id'}), 400
        
        user = Users.query.filter_by(id=user_id).first()
        if user is None:
            return jsonify({'error': 'User not found'}), 404
        else:
            user_data = user.to_dict()
            user_data.pop('password', None) # password 필드는 제외
            return jsonify(user_data), 200
        
    except OperationalError as e:
        return jsonify({'error': str(e)}), 500

# GET /user/user_auth_time API User 테이블의 특정 사용자의 인증 시간 조회
@api_user_bp.route('/user_auth_time', methods=['GET'])
@get_swag_from(yaml_folder, 'user_auth_time.yaml')
def get_user_auth_time():
    try:
        user_id = request.args.get('id').lower()
        
        if user_id is None:
            return jsonify({'error': 'Please provide id'}), 400 # 400: Bad Request
        
        user = Users.query.filter_by(id=user_id).first()
        if user:
            return jsonify(user.time_stamp)
        else:
            return jsonify({'error': 'User not found'}), 404    # 404: Not Found
    except OperationalError as e:
        return jsonify({'error': str(e)}), 500

# GET /user/verify API 사용자 존재 여부 확인 (인증된 사용자용)
@api_user_bp.route('/verify', methods=['GET'])
@jwt_required(locations=['headers','cookies'])  # JWT 검증을 먼저 수행
def verify_user():
    try:
        user_id = request.args.get('id')
        if user_id is None:
            return jsonify({'error': 'Please provide id'}), 400
        
        # Find the user - use case-insensitive search and check is_deleted
        user = Users.query.filter(Users.id.ilike(user_id), Users.is_deleted == False).first()
        
        if user is None:
            return jsonify({'exists': False}), 200
        else:
            # Return user data without password
            return jsonify({
                'exists': True, 
                'user': {
                    'id': user.id,
                    'name': user.name,
                    'company': user.company,
                    'department': user.department,
                    'position': user.position,
                    'access_group_id': user.access_group_id,
                    'role_id': user.role_id,
                    'time_stamp': user.time_stamp,
                    'logout_time': user.logout_time,
                    'login_time': user.login_time
                }
            }), 200
        
    except OperationalError as e:
        return jsonify({'error': str(e)}), 500

     
# POST /user/update_user API Users 테이블 Row Insert/Update API
@api_user_bp.route('/update_user', methods=['POST'])
@get_swag_from(yaml_folder, 'update_user.yaml')
def upsert_user():
    try:
        data = request.get_json() # JSON 데이터를 가져옴
        if not data or 'id' not in data:
            return jsonify({'error': 'Please provide id'}), 400
        
        req_email = data.get('email', '').lower()
        if not req_email:
            return jsonify({'error': 'Email is required'}), 400
        
        user_id = data.get('id').lower()
        login = data.get('login')
        logging.info(f"login: {login}")
        
        trim = lambda v: v.strip() if isinstance(v, str) else v
        user = Users.query.filter(func.lower(Users.email) == req_email).first()       
        #user = Users.query.filter_by(id=user_id).first()
        if user is None:    # 새로운 Row 추가
            
            # 제공된 id(사번)가 다른 사용자에 의해 이미 사용 중인지 확인
            id_exists = db.session.query(Users.id).filter(func.lower(Users.id) == user_id).first() is not None
            if id_exists:
                # 만약 ID가 이미 사용 중이면, 409 Conflict 에러를 반환
                logging.warning(f"Attempted to create a new user with an existing employee ID. Email: '{req_email}', ID: '{user_id}'")
                return jsonify({'error': f"Employee ID '{data.get('id')}' is already in use."}), 409
   
            user = Users(id=user_id)
            user.password = data.get('password')
            if(is_valid('company', data)): user.company = data.get('company')
            if(is_valid('department', data)):
                dept = trim(data.get('department'))
                user.department = dept if dept else None
            if(is_valid('position', data)):
                p = trim(data.get('position'))
                user.position = p if p else None
            if(is_valid('name', data)): 
                n = trim(data.get('name'))
                user.name = n if n else None
            if(is_valid('access_group_id', data)): user.access_group_id = data.get('access_group_id')
            if(is_valid('role_id', data)): user.role_id = data.get('role_id')
            if(is_valid('phone', data)): user.phone = data.get('phone')
            if(is_valid('email', data)): user.email = data.get('email')
            if login is True: user.login_time = datetime.datetime.now(timezone.utc)
            db.session.add(user)
            db.session.commit()
        else:   # Row 업데이트   
            assignee_updates = {}
                     
            if(is_valid('password',data)): user.password = data.get('password')
            if(is_valid('company',data)):user.company = data.get('company')
            if(is_valid('department',data)):
                dept = trim(data.get('department'))
                user.department = dept if dept else None
            if(is_valid('position',data)):
                p = trim(data.get('position'))
                user.position = p if p else None
                prefixes = ('연구원','선임','책임','수석','대리','과장','차장','부장')
                
                raw = p
                s = re.sub(r'\s+', ' ', raw).strip() if raw else ''
                position = ('미지정' if not s else next((p for p in prefixes if s.startswith(p)), re.split(r'[\s(/]', s, 1)[0]))
                assignee_updates['position'] = position
            if(is_valid('name',data)):
                n = trim(data.get('name'))
                user.name = n if n else None
                assignee_updates['name'] = user.name
            if(is_valid('access_group_id',data)):user.access_group_id = data.get('access_group_id')
            if(is_valid('role_id',data)):user.role_id = data.get('role_id')
            if(is_valid('phone',data)):user.phone = data.get('phone')
            if(is_valid('email',data)):user.email = data.get('email')
            if login is True: user.login_time = datetime.datetime.now(timezone.utc)
                       
            # Assignees 테이블 업데이트
            if assignee_updates:
                updated = db.session.query(Assignees).filter_by(user_id=user.id)\
                    .update(assignee_updates, synchronize_session=False)
        
            db.session.commit()
        return jsonify(user.to_dict()), 201
    except OperationalError as e:   # DB 접속 오류 처리
        return jsonify({'error': str(e)}), 500

@api_user_bp.route('/ip_location', methods=['GET'])
def get_test():
    ip=request.args.get('ip')
    url = f"http://ipinfo.io/{ip}/json"
    response = requests.get(url)
    return response.json(), 200

@api_user_bp.route('/organizations', methods=['GET'])
@jwt_required(locations=['headers','cookies'])  # JWT 검증을 먼저 수행
def get_organizations():
    try:
        default_companies = ["PTC", "바론컨설턴트", "삼안", "장헌산업", "한맥기술"]
        
        organizations = db.session.query(Users.company, Users.department).filter(Users.is_deleted == False).distinct().all()
        
        org_map = defaultdict(dict)
        
        for company in default_companies:
            org_map[company] = {}
       
        for company, department in organizations:
            if not company:
                continue
            if not department:
                department = '기타'
            org_map[company][department] = []
            
        return jsonify(org_map), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@api_user_bp.route('/user_by_org', methods=['GET'])
@jwt_required(locations=['headers','cookies'])  # JWT 검증을 먼저 수행
def get_user_by_org():
    try:
        company = request.args.get('company')
        department = request.args.get('department')
        
        if company is None:
            return jsonify({'error': 'Please provide company'}), 400
        
        # 직급별 정렬 우선순위 정의
        pos = func.trim(func.coalesce(Users.position, ''))
        position_order = case(           
            (pos.ilike('사장%'), 1),
            (pos.ilike('부사장%'), 2),
            (pos.ilike('전무이사%'), 3),
            (pos.ilike('상무이사%'), 4),
            (pos.ilike('이사%'), 5),
            (pos.ilike('수석%'), 6),      
            (pos.ilike('책임%'), 7),                           
            (pos.ilike('부장%'), 8),   
            (pos.ilike('선임%'), 9),                             
            (pos.ilike('차장%'), 10),              
            (pos.ilike('과장%'), 11),
            (pos.ilike('대리%'), 12),
            (pos.ilike('연구원%'), 13),
            (pos.ilike('사원%'), 14),
            else_=99  # 미정의 직급은 가장 뒤로
        )
        
        query = db.session.query(Users).filter(Users.company == company, Users.is_deleted == False)                       
        if department:            
            query = query.filter(Users.department == department)
        
        users = query.order_by(position_order, Users.name).all()
        
        seen = set()
        unique_users = []
        for user in users:
            normalized_id = user.id.lower()
            if normalized_id not in seen:
                seen.add(normalized_id)
                unique_users.append({
                    'id': user.id,
                    'name': user.name,
                    'company': user.company,
                    'department': user.department,
                    'position': user.position
                })
                
        return jsonify(unique_users), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    
@api_user_bp.route('/search', methods=['GET'])
@jwt_required(locations=['headers','cookies'])  # JWT 검증을 먼저 수행
def get_search():
    try:
        keyword = request.args.get('keyword','').lower().strip()
        if keyword is None:
            return jsonify({'error': 'Please provide keyword'}), 400
        
        result_map = defaultdict(lambda: defaultdict(list))
        seen = set()
        
        users = db.session.query(Users.id,
                                Users.name,
                                Users.company,
                                Users.department,
                                Users.position,
                                Users.email,
                                Users.role_id).filter(
                                    Users.is_deleted == False,
                                    or_(
                                        func.lower(Users.id).like(f'%{keyword}%'),
                                        func.lower(Users.company).like(f'%{keyword}%'),
                                        func.lower(Users.department).like(f'%{keyword}%'),
                                        func.lower(Users.name).like(f'%{keyword}%'),
                                        func.lower(Users.position).like(f'%{keyword}%')
                                    )
                                ).all()
        
        logging.debug(f"Users: {users}")
                                
        for u in users:
            company = u.company or ''
            department = u.department or ''
            norm_id = u.id.lower()
            key = (company, department, norm_id)
            
            if keyword in (company.lower(), department.lower()):
                result_map[company][department]
            
            if (keyword in (u.name or '').lower() or 
                keyword in norm_id or 
                keyword in (u.position or '').lower()) and key not in seen:
                result_map[company][department].append({
                    'id': u.id,
                    'name': u.name,
                    'company': company,
                    'department': department,
                    'position': u.position,
                    'email': u.email,
                    'role_id': u.role_id
                })
                seen.add(key)
                
        return jsonify(result_map), 200 
    except Exception as e:
        logging.error(f"[get_search] error: {str(e)}, {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


# GET /user/get_external_ips API 외부 IP 조회
@api_user_bp.route('/get_external_ips', methods=['GET'])
@jwt_required(locations=['headers','cookies'])  # JWT 검증을 먼저 수행
def get_external_ips():
    try:
        period_type = request.args.get('period_type', 'day')
        period_value = request.args.get('period_value')
        if period_value is None:
            return jsonify({'error': 'Please provide period_value'}), 400
        
        filter_type = request.args.get('filter_type', 'all')
        filter_value = request.args.get('filter_value')
        if filter_type != 'all' and filter_value is None:
            return jsonify({'error': 'Please provide filter_value'}), 400
        
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 10, type=int)
        offset = (page - 1) * page_size
        
        start_date,end_date = summary_service.get_period_value(period_type, period_value)  # Validate period_value
        local_tz = datetime.datetime.now().astimezone().tzinfo
        utc_start_date = datetime.datetime.combine(start_date, datetime.time.min, tzinfo=local_tz).astimezone(datetime.timezone.utc)
        utc_end_date = datetime.datetime.combine(end_date, datetime.time.max, tzinfo=local_tz).astimezone(datetime.timezone.utc)

        query = db.session.query(
            LoginHistory.user_id,
            LoginHistory.ip_address,
            Users.name.label('user_name'),
            LoginHistory.login_time
        ).join(
            Users, LoginHistory.user_id == Users.id
        ).filter(
            LoginHistory.login_time >= utc_start_date,
            LoginHistory.login_time <= utc_end_date,
        )
        
        if filter_type == 'user':
            query = query.filter(LoginHistory.user_id == filter_value.lower())
        elif filter_type == 'company':
            query = query.filter(Users.company == filter_value)
        elif filter_type == 'department':
            part = filter_value.split('||',1)
            if len(part) == 2:
                query = query.filter(Users.company == part[0], Users.department == part[1])
            else:
                query = query.filter(Users.department == filter_value)
               
        query = query.filter(
            LoginHistory.ip_address.isnot(None),
            LoginHistory.ip_address != '',
            ~exists().where(
                cast(LoginHistory.ip_address, INET).between(
                    cast(IpRange.start_ip, INET),
                    cast(IpRange.end_ip, INET)
                )
            )
        )
        
        total = query.distinct().count()
        rows = query.distinct().order_by(LoginHistory.login_time.desc()).offset(offset).limit(page_size).all()
        
        return jsonify({
            'total': total,
            'page': page,
            'page_size': page_size,
            'data': [
                {
                    'user_id': row.user_id,
                    'ip_address': row.ip_address,
                    'user_name': row.user_name,
                    'login_time': row.login_time.isoformat() if row.login_time else None
                } for row in rows
            ] 
        })

    except Exception as e:
        logging.error(f"[get_external_ips] error: {str(e)}, {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# GET /user/get_latest_login_time API 사용자 최신 로그인 시간 조회
@api_user_bp.route('/get_latest_login_time', methods=['GET'])
@jwt_required(locations=['headers','cookies'])  # JWT 검증을 먼저 수행
def get_latest_login_time():
    try:
        user_id = get_jwt_identity()
        if user_id is None:
            return jsonify({'error': 'Please provide id'}), 400
        
        user = LoginHistory.query.filter_by(user_id=user_id).order_by(LoginHistory.login_time.desc()).first()        
        
        if user:
            return jsonify({
                'latest_login_time': user.login_time.isoformat() if user.login_time else None
            }), 200
        else:
            # 사용자 로그인 이력이 없는 경우
            return jsonify({'latest_login_time': None}), 404

    except Exception as e:
        logging.error(f"[get_latest_login_time] error: {str(e)}, {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500
    
@api_user_bp.route('/companies', methods=['GET'])
@jwt_required(locations=['headers','cookies'])
def get_companies():
    """
    Get all unique companies from users table
    """
    try:
        # Query for distinct companies, excluding empty or null values
        companies = db.session.query(Users.company).filter(
            Users.is_deleted == False,
            Users.company.isnot(None),
            Users.company != ''
        ).distinct().order_by(Users.company).all()
        
        # Extract company names from query result
        company_list = [company[0] for company in companies]
        
        return jsonify(company_list)
    except Exception as e:
        logging.error(f"Error fetching companies: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_user_bp.route('/departments', methods=['GET'])
@jwt_required(locations=['headers','cookies'])
def get_departments():
    """
    Get all departments for a specific company
    """
    try:
        company = request.args.get('company')
        if not company:
            return jsonify({'error': 'Company parameter is required'}), 400
            
        # Query for distinct departments in the specified company
        departments = db.session.query(Users.department).filter(
            Users.company == company,
            Users.is_deleted == False,
            Users.department.isnot(None),
            Users.department != ''
        ).distinct().order_by(Users.department).all()
        
        # Extract department names from query result
        department_list = [dept[0] for dept in departments]
        
        return jsonify(department_list)
    except Exception as e:
        logging.error(f"Error fetching departments: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_user_bp.route('/positions', methods=['GET'])
@jwt_required(locations=['headers','cookies'])
def get_positions():
    """
    Get all positions for a specific company and department
    """
    try:
        company = request.args.get('company')
        department = request.args.get('department')
        
        if not company or not department:
            return jsonify({'error': 'Company and department parameters are required'}), 400
            
        # Query for distinct positions in the specified company and department
        positions = db.session.query(Users.position).filter(
            Users.company == company,
            Users.department == department,
            Users.is_deleted == False,
            Users.position.isnot(None),
            Users.position != ''
        ).distinct().order_by(Users.position).all()
        
        # Extract position names from query result
        position_list = [pos[0] for pos in positions]
        
        return jsonify(position_list)
    except Exception as e:
        logging.error(f"Error fetching positions: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_user_bp.route('/names', methods=['GET'])
@jwt_required(locations=['headers','cookies'])
def get_names():
    """
    Get all users for a specific company, department, and position
    """
    try:
        company = request.args.get('company')
        department = request.args.get('department')
        position = request.args.get('position')
        
        if not company or not department or not position:
            return jsonify({'error': 'Company, department, and position parameters are required'}), 400
            
        # Query for users in the specified company, department, and position
        users = db.session.query(Users.id, Users.name).filter(
            Users.company == company,
            Users.department == department,
            Users.position == position,
            Users.is_deleted == False
        ).order_by(Users.name).all()
        
        # Format user data
        user_list = [{'id': user.id, 'name': user.name} for user in users]
        
        return jsonify(user_list)
    except Exception as e:
        logging.error(f"Error fetching user names: {str(e)}")
        return jsonify({'error': str(e)}), 500

