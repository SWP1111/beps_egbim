import logging
import log_config
import datetime
import os
import requests
from datetime import timezone
from extensions import db
from flask import jsonify, request, make_response
from flask_jwt_extended import create_access_token, decode_token, get_jwt, get_jwt_identity, jwt_required
from sqlalchemy.exc import OperationalError
from utils.swagger_loader import get_swag_from
from models import Users, LoginHistory
from . import api_user_bp, yaml_folder


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
        if not user:
            return jsonify({'error': 'User not found'}), 404 # 404: Not Found
        
        if user.is_deleted == True:
            Users.query.filter_by(id=user_id).update({'is_deleted': False}) # 비활성화된 사용자는 활성화 처리
            db.session.commit()  # 변경 사항 커밋 
                                                            
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
        
        return response, 200 # 200: OK
    except OperationalError as e:
        return jsonify({'error': str(e)}), 500  # 500: Internal Server Error
    
    
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
    
    
@api_user_bp.route('/emp_status', methods=['POST'])
@get_swag_from(yaml_folder, 'emp_status.yaml')
def emp_status():
    try:
        logging.debug(f"요청 헤더: {dict(request.headers)}")
        allow_ip = "183.111.138.248" # 허용된 IP 주소
        client_ip_raw = request.headers.get('X-Forwarded-For', request.remote_addr)
        client_ip_list = [ip.strip() for ip in client_ip_raw.split(',')]
        logging.debug(f"클라이언트 IP: {client_ip_list}")
        
#        if allow_ip not in client_ip_list:
#            logging.warning(f"접근 거부: 허용되지 않은 IP {client_ip_raw}")
#            return jsonify({'error': 'Invalid client IP', 'your Ip': client_ip_raw}), 403

        data = request.get_json() # JSON 데이터를 가져옴
        employee_email = data.get('email').strip().lower() if data.get('email') else None
        status = data.get('status')
        
        if not employee_email or not status:
            return jsonify({'error': 'Please provide employee email and status'}), 400
        
        user = Users.query.filter_by(email=employee_email).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if status == 'inactive':
            # 비활성화 처리 로직  
            user.is_deleted = True
            db.session.commit()
            return jsonify({'email': f'{employee_email}', 'status': 'inactive'}), 200
        elif status == 'active':
            user.is_deleted = False
            db.session.commit()
            return jsonify({'email': f'{employee_email}', 'status': 'active'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
