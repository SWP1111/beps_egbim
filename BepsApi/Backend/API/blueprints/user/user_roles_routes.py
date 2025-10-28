import logging
import log_config
import datetime
import os
import requests
from datetime import timezone
from extensions import db
from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import OperationalError
from sqlalchemy import or_
from utils.swagger_loader import get_swag_from
from models import Roles, Users
from . import api_user_bp, yaml_folder
          
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


# GET /user/users_by_role API 권한별 사용자 조회
@api_user_bp.route('/users_by_role', methods=['GET'])
@jwt_required(locations=['headers','cookies'])  # JWT 검증을 먼저 수행
def get_users_by_role():
    """
    권한별 사용자 조회 API
    Query Parameters:
    - role_id: 권한 ID (1: 통합관리자, 2: 개발관리자, ~~3: Content_관리자(삭제됨), 4: Content_실무자(삭제됨)~~, 5: 일반사용자(사내), 6: 일반사용자(사외))
             비어있으면 전체 사용자 조회
    
    Returns:
    - users: 해당 권한을 가진 사용자 목록 또는 전체 사용자 목록
    """
    try:
        role_id = request.args.get('role_id')
        
        # 권한명 매핑
        role_names = {
            1: '통합관리자',
            2: '개발관리자', 
            # 3: 'Content_관리자',
            # 4: 'Content_실무자',
            5: '일반사용자(사내)',
            6: '일반사용자(사외)'
        }
        
        # role_id가 None이면 전체 사용자 조회
        if role_id is None:
            users = Users.query.filter(Users.is_deleted != True).all()
            role_filter_info = {
                'role_id': None,
                'role_name': '전체',
                'total_count': len(users)
            }
        else:
            try:
                role_id = int(role_id)
            except ValueError:
                return jsonify({'error': 'role_id must be an integer'}), 400
            
            # 유효한 role_id 범위 체크
            if role_id not in [1, 2, 5, 6]:
                return jsonify({'error': 'role_id must be between 1 and 6'}), 400
            
            # role_id가 5인 경우 NULL인 사용자도 포함
            if role_id == 5:
                users = Users.query.filter(
                    or_(Users.role_id == role_id, Users.role_id.is_(None)),
                    Users.is_deleted != True
                ).all()
            else:
                users = Users.query.filter_by(role_id=role_id, is_deleted=False).all()
            
            role_filter_info = {
                'role_id': role_id,
                'role_name': role_names[role_id],
                'total_count': len(users)
            }
        
        users_data = []
        for user in users:
            user_dict = user.to_dict()
            user_dict.pop('password', None)  # 비밀번호 제외
            
            # role_id가 NULL인 경우 5로 설정
            if user_dict['role_id'] is None:
                user_dict['role_id'] = 5
                user_dict['role_name'] = role_names[5]
            else:
                user_dict['role_name'] = role_names.get(user_dict['role_id'], '알 수 없음')
            
            users_data.append(user_dict)
        
        response_data = {
            'role_id': role_filter_info['role_id'],
            'role_name': role_filter_info['role_name'],
            'total_count': len(users_data),
            'users': users_data
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logging.error(f"Error in get_users_by_role: {str(e)}")
        return jsonify({'error': str(e)}), 500


# POST /user/update_permission API 사용자 권한 업데이트
@api_user_bp.route('/update_permission', methods=['POST'])
@jwt_required(locations=['headers','cookies'])  # JWT 검증을 먼저 수행
def update_user_permission():
    """
    사용자 권한 업데이트 API
    Request Body:
    {
        "user_id": "직원ID",
        "role_id": 권한ID (1-6)
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data is required'}), 400
        
        user_id = data.get('user_id')
        role_id = data.get('role_id')
        
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        
        if role_id is None:
            return jsonify({'error': 'role_id is required'}), 400
        
        # role_id 유효성 검사
        if not isinstance(role_id, int) or role_id not in [1, 2, 5, 6]:
            return jsonify({'error': 'role_id must be an integer between 1 and 6'}), 400
        
        # 사용자 존재 여부 확인
        user = Users.query.filter_by(id=user_id, is_deleted=False).first()
        if not user:
            return jsonify({'error': 'User not found or inactive'}), 404
        
        # 권한 업데이트
        old_role_id = user.role_id
        user.role_id = role_id
        db.session.commit()
        
        # 권한명 매핑
        role_names = {
            1: '통합관리자',
            2: '개발관리자', 
            # 3: 'Content_관리자',
            # 4: 'Content_실무자',
            5: '일반사용자(사내)',
            6: '일반사용자(사외)'
        }
        
        logging.info(f"Permission updated: user_id={user_id}, old_role_id={old_role_id}, new_role_id={role_id}")
        
        response_data = {
            'success': True,
            'message': f'{user.name}님의 권한이 {role_names.get(role_id, "알 수 없음")}로 변경되었습니다.',
            'user': {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'company': user.company,
                'department': user.department,
                'position': user.position,
                'old_role_id': old_role_id,
                'new_role_id': role_id,
                'role_name': role_names.get(role_id, '알 수 없음')
            }
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logging.error(f"Error in update_user_permission: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
