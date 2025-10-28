import logging
import os
import log_config
import decryption
from flask import Blueprint, jsonify, request, make_response
from flask_jwt_extended import create_access_token, decode_token, get_csrf_token, jwt_required, get_jwt_identity, verify_jwt_in_request, get_jwt
import datetime
from datetime import timezone
from extensions import db
from models import Users, Roles, ContentAccessGroups, LoginHistory, loginSummaryDay, loginSummaryAgg, IpRange
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

api_user_bp = Blueprint('user', __name__)

yaml_folder = os.path.join(os.path.dirname(__file__), '..', 'docs', 'user')

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


# GET /user/token_check API 토큰(쿠키) 유효 체크
@api_user_bp.route('/token_check', methods=['GET'])
@jwt_required(locations=['headers','cookies'])  # JWT 검증을 먼저 수행
@get_swag_from(yaml_folder, 'token_check.yaml')
def check():
    current_user = get_jwt_identity()
    
    if current_user:
        from config import Config
        env = Config.ENV == 'production' # 운영 환경인지 확인
        response = jsonify({"success": True, "user": current_user})
        access_token = create_access_token(identity=current_user, expires_delta=datetime.timedelta(days=1))
        response.set_cookie(
            'access_token_cookie',     # 쿠키 이름
            access_token,       # 쿠키 값
            httponly=True,      # JS에서 쿠키 접근 금지
            secure=env,       # HTTPS에서만 쿠키 전송(False: HTTP에서도 전송)
            samesite='Lax',      # SameSite 설정(Lax: 외부 도메인으로는 쿠키 전송 안 함)
            expires=(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1)) # 1일 유효
        )
        return response, 200
    else:
        return jsonify({"success": False, "error":"Invalid token"}), 401

# GET /user/csrf_token API CSRF 토큰 조회
@api_user_bp.route('/csrf_token', methods=['GET'])
@jwt_required(locations=['cookies'])  # JWT 검증을 먼저 수행
@get_swag_from(yaml_folder, 'csrf_token.yaml')
def get_csrf_token_route():
    token = request.cookies.get('access_token_cookie')
    if not token:
        return jsonify({'error': 'No access token found'}), 401
    
    decoded = decode_token(token)
    csrf_token = decoded.get('csrf')
    if not csrf_token:
        return jsonify({'error': 'No CSRF token found'}), 401
    return jsonify({'csrf_token': csrf_token}), 200

# POST /user/user API Users 테이블 Row 조회 API (로그인)
@api_user_bp.route('/user', methods=['POST'])
@get_swag_from(yaml_folder, 'user.yaml')
def get_user():
    try:
        data = request.get_json() # JSON 데이터를 가져옴
        logging.info(f"POST /user: {data}")
        
        user_id = data.get('id').lower()
        id_address = data.get('ip_address')
        descope_refreshJwt = data.get('descope_refresh_jwt', None)
                
        if not user_id:
            return jsonify({'error': 'Please provide id'}), 400 # 400: Bad Request
        if not descope_refreshJwt:
            return jsonify({'error': 'Please provide descope_refresh_jwt'}), 400
        
        descope_header = {
            'Authorization': f'Bearer P2wON5fy1K6kyia269VpeIzYP8oP:{descope_refreshJwt}' # Descope 프로젝트 ID와 Refresh JWT를 사용하여 인증
        }
        descope_response = requests.post('https://api.descope.com/v1/auth/validate', headers=descope_header)
        if descope_response.status_code != 200:
            return jsonify({'error': 'Invalid descope_refresh_jwt'}), 401 # 401: Unauthorized
        
        user = Users.query.filter_by(id=user_id).first()
        
        if user:                                               
            user_data = user.to_dict()
            user_data.pop('password', None) # password 필드는 제외
                        
            ua = (request.headers.get('User-Agent') or '').lower()
            logging.debug(f"User-Agent: {ua}")
            
            #로그인 이력 저장
            if not ua:               
                login_history = LoginHistory(user_id=user_id, login_time=datetime.datetime.now(timezone.utc), ip_address=id_address) 
                db.session.add(login_history)
                db.session.commit()
                       
                access_token = create_access_token(identity=user_id, additional_claims={'login_id':login_history.id}, expires_delta=datetime.timedelta(days=1)) # 1일 유효한 access token 생성
            else:
                access_token = create_access_token(identity=user_id, expires_delta=datetime.timedelta(days=1))
            response = jsonify({"user":user_data, "token":access_token})
            
            # 웹에서는 쿠키 설정
            if any(browser in ua for browser in ['chrome', 'safari', 'edge', 'opr', 'firefox']):  #"web" in request.headers.get('User-Agent',"").lower():                        
                from config import Config
                env = Config.ENV == 'production' # 운영 환경인지 확인
                response.set_cookie(
                    'access_token_cookie',     # 쿠키 이름
                    access_token,       # 쿠키 값
                    httponly=True,      # JS에서 쿠키 접근 금지
                    secure=env,       # HTTPS에서만 쿠키 전송(False: HTTP에서도 전송)
                    samesite='Lax',      # SameSite 설정(Lax: 외부 도메인으로는 쿠키 전송 안 함)
                    expires=(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1)) # 1일 유효
                )
                #response.json['csrf_token'] = get_csrf_token(access_token) # CSRF 토큰 추가
            
            return response
        else:
            return jsonify({'error': 'User not found'}), 404    # 404: Not Found
    except OperationalError as e:
        return jsonify({'error': str(e)}), 500  # 500: Internal Server Error

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
        
        user_id = data.get('id').lower()
        login = data.get('login')
        logging.info(f"login: {login}")
        
        user = Users.query.filter_by(id=user_id).first()
        if user is None:    # 새로운 Row 추가
            user = Users(id=user_id)
            user.password = data.get('password')
            if(is_valid('company', data)): user.company = data.get('company')
            if(is_valid('department', data)): user.department = data.get('department')
            if(is_valid('position', data)): user.position = data.get('position')
            if(is_valid('name', data)): user.name = data.get('name')
            if(is_valid('access_group_id', data)): user.access_group_id = data.get('access_group_id')
            if(is_valid('role_id', data)): user.role_id = data.get('role_id')
            if(is_valid('phone', data)): user.phone = data.get('phone')
            if(is_valid('email', data)): user.email = data.get('email')
            if login is True: user.login_time = datetime.datetime.now(timezone.utc)
            db.session.add(user)
            db.session.commit()
        else:   # Row 업데이트
            if(is_valid('password',data)): user.password = data.get('password')
            if(is_valid('company',data)):user.company = data.get('company')
            if(is_valid('department',data)):user.department = data.get('department')
            if(is_valid('position',data)):user.position = data.get('position')
            if(is_valid('name',data)):user.name = data.get('name')
            if(is_valid('access_group_id',data)):user.access_group_id = data.get('access_group_id')
            if(is_valid('role_id',data)):user.role_id = data.get('role_id')
            if(is_valid('phone',data)):user.phone = data.get('phone')
            if(is_valid('email',data)):user.email = data.get('email')
            if login is True: user.login_time = datetime.datetime.now(timezone.utc)
            db.session.commit()
        return jsonify(user.to_dict()), 201
    except OperationalError as e:   # DB 접속 오류 처리
        return jsonify({'error': str(e)}), 500

# GET /user/logout API 사용자 로그아웃 API
@api_user_bp.route('/logout', methods=['GET'])
@jwt_required(locations=['headers','cookies'])  # JWT 검증을 먼저 수행
@get_swag_from(yaml_folder, 'logout.yaml')
def logout():  
    try:
        user_id = get_jwt_identity()
        claims = get_jwt()
        
        login_id = claims.get('login_id')
        logging.info(f"login_id: {login_id}")
        
        logout_update =  request.args.get('logout_update', 'false').lower() == 'true'
        
        if not user_id:
            return jsonify({'error': 'Please provide id'}), 400
    
        user = Users.query.filter_by(id=user_id).first()
    
        # 로그인 이력 업데이트
        if login_id:
            login = LoginHistory.query.filter_by(id=login_id).first()
            if login:
                login.logout_time = datetime.datetime.now(timezone.utc)
                duration = login.logout_time - login.login_time
                
                if duration.total_seconds() < 30:
                    db.session.delete(login) # 로그인 이력이 30초 미만이면 삭제             
                
                db.session.commit()
            
        if user:
            if logout_update is True:
                user.logout_time = datetime.datetime.now(timezone.utc) # 로그아웃 시간 업데이트(UTC)
                db.session.commit()
            
            response = make_response(jsonify({'message': f'User {user_id} logged out successfully.', 'logout_time': user.logout_time}))
            response.set_cookie('access_token_cookie', '', expires=0, httponly=True, secure=False, samesite='Lax') # 쿠키 삭제
            
            return response, 200
        else:
            return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
          
# GET /user/roles API Roles 테이블 조회
@api_user_bp.route('/roles', methods=['GET'])
@get_swag_from(yaml_folder, 'roles.yaml')
def get_roles():
    try:
        roles = Roles.query.all()
        return jsonify([role.to_dict() for role in roles])
    except OperationalError as e:
        return jsonify({'error': str(e)}), 500

# POST /user/roles API Roles 테이블 Row 추가
@api_user_bp.route('/roles', methods=['POST'])
def create_role():
    try:
        data = request.get_json() # JSON 데이터를 가져옴
        if not data or 'role_name' not in data:
            return jsonify({'error': 'Please provide role_name'}), 400
        
        new_role = Roles(role_name=data.get('role_name'))
        db.session.add(new_role)
        db.session.commit()
        return jsonify(new_role.to_dict()), 201
    except OperationalError as e:   # DB 접속 오류 처리
        return jsonify({'error': str(e)}), 500
    except Exception as e:  # 그 외 오류 처리
        return jsonify({'error': str(e)}), 500

# POST /user/erp_login API ERP Login
@api_user_bp.route('/erp_login', methods=['POST'])
def erp_login():
    try:
        data = request.get_json() # JSON 데이터를 가져옴
        targetUrl = data.get('targetUrl')
        params = data.get('params')
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        
        # ERP 로그인 API 호출
        response = requests.post(targetUrl, headers=headers, data=params)
        logging.info(f"ERP Login Response: {response.text} {response.status_code} {response.headers}")
        logging.info(f"ERP Login Cookies: {response.cookies}")
        logging.info(f"ERP Login Set-Cookie Headers: {response.headers.get('Set-Cookie')}")
        
        # 응답 데이터와 상태 코드 반환
        return jsonify({"status": response.status_code, "data": response.text}), response.status_code

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_user_bp.route('/get_connection_duration', methods=['GET'])
@jwt_required(locations=['headers','cookies'])  # JWT 검증을 먼저 수행
def get_connection_duration():
    try:
        filter_type = request.args.get('filter_type', 'all')
        filter_value = request.args.get('filter_value')
        if filter_value:
            filter_value = unquote(filter_value)
        
        if filter_type != 'all' and filter_value is None:
            return jsonify({'error': 'Please provide filter_value'}), 400
               
        period_type = request.args.get('period_type', 'day')
        period_value = request.args.get('period_value')
        
        if period_value is None:
            return jsonify({'error': 'Please provide period_value'}), 400
        
        if(period_type == 'day'):
            start_date, end_date = [datetime.datetime.strptime(d.strip(), '%Y-%m-%d').date() for d in period_value.split('~')]
            data = summary_service.get_connection_summary_mixed(start_date, end_date, filter_type, filter_value)
                                
            if data['has_data']:
                return jsonify({
                    'total_duration': data['total_duration'].total_seconds(),
                    'worktime_duration': data['worktime_duration'].total_seconds(),
                    'offhour_duration': data['offhour_duration'].total_seconds(),
                    'internal_count': data['internal_count'],
                    'external_count': data['external_count']
                })
            else:    
                return jsonify({'error': 'No data available for given parameters'}), 404     
        elif(period_type in ['quarter', 'half', 'year']):
            data = summary_service.get_connection_summary_agg(period_type, period_value, filter_type, filter_value)
            
            if data['has_data']:
                return jsonify({
                    'total_duration': data['total_duration'].total_seconds(),
                    'worktime_duration': data['worktime_duration'].total_seconds(),
                    'offhour_duration': data['offhour_duration'].total_seconds(),
                    'internal_count': data['internal_count'],
                    'external_count': data['external_count']
                })
            else:
                start_date,end_date = summary_service.get_period_value(period_type, period_value)                     
                data = summary_service.get_connection_summary_mixed(start_date, end_date, filter_type, filter_value)
                               
                if data['has_data']:
                    return jsonify({
                        'total_duration': data['total_duration'].total_seconds(),
                        'worktime_duration': data['worktime_duration'].total_seconds(),
                        'offhour_duration': data['offhour_duration'].total_seconds(),
                        'internal_count': data['internal_count'],
                        'external_count': data['external_count']
                    })
                else:    
                    return jsonify({'error': 'No data available for given parameters'}), 404 
        
        return jsonify({'error': f"Invalid period_type. Allowed values are: day, quarter, half, year."}), 400
             
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    
@api_user_bp.route('/get_top_user_duration', methods=['GET'])
@jwt_required(locations=['headers','cookies'])  # JWT 검증을 먼저 수행
def get_top_user_duration():
    try:
        period_type = request.args.get('period_type', 'day')
        period_value = request.args.get('period_value')
        
        if period_value is None:
            return jsonify({'error': 'Please provide period_value'}), 400        
        
        if period_type == 'day':
            start_date, end_date = [datetime.datetime.strptime(d.strip(), '%Y-%m-%d').date() for d in period_value.split('~')]           
            data = summary_service.get_top_user_duration_mixed(start_date, end_date)
            logging.info(f"get_top_user_duration_mixed: {data}")
            
            if data['has_data']:
                response = {'data': data}
                return jsonify(response),200
            else:
                return jsonify({'error': 'No data found'}), 404        
            
        elif period_type in ['quarter', 'half', 'year']:            
            user_duration_map = {}
            
            all_user = db.session.query(Users.id, Users.name).all()
            for user in all_user:
                user_duration_map[user.id.lower()] = (user.name, 0)
                
            summary_day_rows = summary_service.get_summary_rows_agg(
                loginSummaryAgg,
                period_type = period_type,
                period_value = period_value,
                join_users=True,
                group_fields=[loginSummaryAgg.user_id, Users.name]
            )
           
            if summary_day_rows:
                for record in summary_day_rows:
                    if record.user_id:
                        prev = user_duration_map.get(record.user_id.lower())
                        duration = (record.total.total_seconds() if record.total else 0)
                        if prev:
                            user_duration_map[record.user_id.lower()] = (record.name, prev[1] + duration)
                        else:
                            user_duration_map[record.user_id.lower()] = (record.name, duration)
                            
                if (len(user_duration_map) > 0):
                    sorted_user = sorted(user_duration_map.items(), key=lambda x: x[1][1], reverse=True)
                    sorted_users_by_low = sorted(user_duration_map.items(), key=lambda x: x[1][1])
                    response = {
                        'data': {
                            'top': [(user_id, name, duration) for user_id, (name, duration) in sorted_user[:3]],
                            'bottom': [(user_id, name, duration) for user_id, (name, duration) in sorted_users_by_low[:3]],
                        }
                    }
                    return jsonify(response),200
                else:
                    return jsonify({'error': 'No data found'}), 404
            
            else:
                start_date,end_date = summary_service.get_period_value(period_type, period_value) 
                data = summary_service.get_top_user_duration_mixed(start_date, end_date)
                logging.info(f"get_top_user_duration_mixed: {data}")
                
                if data['has_data']:
                    response = {'data': data}
                    return jsonify(response),200
                else:
                    return jsonify({'error': 'No data found'}), 404 
                                    
    except Exception as e:
        logging.error(f"예외 발생: {str(e)}, {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@api_user_bp.route('/get_top_department_duration', methods=['GET'])
@jwt_required(locations=['headers','cookies'])  # JWT 검증을 먼저 수행
def get_top_department_duration():
    try:
        period_type = request.args.get('period_type', 'day')
        period_value = request.args.get('period_value')
        
        if period_value is None:
            return jsonify({'error': 'Please provide period_value'}), 400
            
        if period_type == 'day':
            start_date, end_date = [datetime.datetime.strptime(d.strip(), '%Y-%m-%d').date() for d in period_value.split('~')]           
            data = summary_service.get_top_department_duration_mixed(start_date, end_date)
            logging.info(f"get_top_department_duration_mixed: {data}")
            
            if data['has_data']:
                response = {'data': data}
                return jsonify(response),200
            else:
                return jsonify({'error': 'No data found'}), 404
        elif period_type in ['quarter', 'half', 'year']:
            dept_duration_map = {}
            
            all_dept = db.session.query(Users.company, Users.department).all()
            for company, department in all_dept:
                dept_duration_map[(company, department)] = 0
                
            summary_rows = summary_service.get_summary_rows_agg(
                loginSummaryAgg,
                period_type = period_type,
                period_value = period_value,
                group_fields=[loginSummaryAgg.company, loginSummaryAgg.department]
            )
            
            if summary_rows:
                for row in summary_rows:
                    logging.debug(f"Row: {row}")
                    key = (row.company, row.department)
                    if dept_duration_map.get(key):
                        dept_duration_map[key] += (row.total.total_seconds() if row.total else 0)
                    else:
                        dept_duration_map[key] = (row.total.total_seconds() if row.total else 0)
                
                if(len(dept_duration_map) > 0):
                    sorted_dept = sorted(dept_duration_map.items(), key=lambda x: x[1], reverse=True)
                    sorted_dept_by_low = sorted(dept_duration_map.items(), key=lambda x: x[1])
                    response = {
                        'data': {
                            'top': [(company, department, duration) for (company, department), duration in sorted_dept[:3]],
                            'bottom': [(company, department, duration) for (company, department), duration in sorted_dept_by_low[:3]],
                        }
                    }
                    return jsonify(response),200
                else:
                    return jsonify({'error': 'No data found'}), 404
            else:
                start_date,end_date = summary_service.get_period_value(period_type, period_value) 
                data = summary_service.get_top_department_duration_mixed(start_date, end_date)
                
                if data['has_data']:
                    response = {'data': data}
                    return jsonify(response),200
                else:
                    return jsonify({'error': 'No data found'}), 404
            
    except Exception as e:
        return jsonify({'[get_top_department_duration] error': str(e)}), 500    

@api_user_bp.route('/get_top_company_duration', methods=['GET'])
@jwt_required(locations=['headers','cookies'])  # JWT 검증을 먼저 수행
def get_top_company_duration():
    try:
        period_type = request.args.get('period_type', 'day')
        period_value = request.args.get('period_value')
        
        if period_value is None:
            return jsonify({'error': 'Please provide period_value'}), 400
            
        if period_type == "day":
            start_date, end_date = [datetime.datetime.strptime(d.strip(), '%Y-%m-%d').date() for d in period_value.split('~')]
            data = summary_service.get_top_company_duration_mixed(start_date, end_date)
            
            if data['has_data']:
                response = {'data': data}
                return jsonify(response),200
            else:                    
                return jsonify({'error': 'No data found'}), 404
        elif period_type in ['quarter', 'half', 'year']:
            company_duration_map = {}
            
            all_company = db.session.query(Users.company).distinct().all()
            for (company,) in all_company:
                company_duration_map[company] = 0
                
            summary_rows = summary_service.get_summary_rows_agg(
                loginSummaryAgg,
                period_type= period_type,
                period_value= period_value,
                group_fields=[loginSummaryAgg.company]
            )
            
            if summary_rows:
                for row in summary_rows:
                    if company_duration_map.get(row.company):
                        company_duration_map[row.company] += (row.total.total_seconds() if row.total else 0)
                    else:
                        company_duration_map[row.company] = (row.total.total_seconds() if row.total else 0)

                if(len(company_duration_map) > 0):
                    sorted_company = sorted(company_duration_map.items(), key=lambda x: x[1], reverse=True)
                    sorted_company_by_low = sorted(company_duration_map.items(), key=lambda x: x[1])
                    response = {
                        'data': {
                            'top': [(company, duration) for company, duration in sorted_company[:3]],
                            'bottom': [(company, duration) for company, duration in sorted_company_by_low[:3]],
                        }
                    }
                    return jsonify(response),200
                else:                    
                    return jsonify({'error': 'No data found'}), 404
            else:
                start_date,end_date = summary_service.get_period_value(period_type, period_value) 
                data = summary_service.get_top_company_duration_mixed(start_date, end_date)
                
                if data['has_data']:
                    response = {'data': data}
                    return jsonify(response),200
                else:                    
                    return jsonify({'error': 'No data found'}), 404
            
    except Exception as e:
        logging.error(f"[get_top_company_duration] error: {str(e)}, {traceback.format_exc()}")
        return jsonify({'[get_top_company_duration] error': str(e)}), 500


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
        organizations = db.session.query(Users.company, Users.department).distinct().all()
        
        org_map = defaultdict(dict)
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
        position_order = case(           
            (Users.position == '사장', 1),
            (Users.position == '부사장', 2),
            (Users.position == '전무이사', 3),
            (Users.position == '상무이사', 4),
            (Users.position == '이사', 5),
            (Users.position == '수석', 6),      
            (Users.position == '책임', 7),                           
            (Users.position == '부장', 8),   
            (Users.position == '선임', 9),                             
            (Users.position == '차장', 10),              
            (Users.position == '과장', 11),
            (Users.position == '대리', 12),
            (Users.position == '연구원', 13),
            (Users.position == '사원', 14),
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
                                Users.position).filter(
                                    Users.is_deleted == False,
                                    or_(
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
            
            if keyword in (u.name or '').lower() and key not in seen:
                result_map[company][department].append({
                    'id': u.id,
                    'name': u.name,
                    'company': company,
                    'department': department,
                    'position': u.position
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
            LoginHistory.login_time < utc_end_date,
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

