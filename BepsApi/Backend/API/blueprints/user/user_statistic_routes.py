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
from . import api_user_bp, yaml_folder



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
        
        start_date, end_date = summary_service.get_period_value(period_type, period_value)
        
        # LoginHistory 테이블에서 고유 IP 개수만 가져오기
        ip_counts = summary_service.get_unique_ip_counts(start_date, end_date, filter_type, filter_value)
        logging.info(f"IP Counts: {ip_counts}")
        
        duration_data = None
        if(period_type == 'day'):
            duration_data = summary_service.get_connection_summary_mixed(start_date, end_date, filter_type, filter_value)   
        elif(period_type in ['quarter', 'half', 'year']):
            duration_data = summary_service.get_connection_summary_agg(period_type, period_value, filter_type, filter_value)
            
            if not duration_data['has_data']:                   
                duration_data = summary_service.get_connection_summary_mixed(start_date, end_date, filter_type, filter_value)
        else:
            return jsonify({'error': f"Invalid period_type. Allowed values are: day, quarter, half, year."}), 400
        
        if duration_data and (duration_data['has_data'] or ip_counts['internal_count'] > 0 or ip_counts['external_count'] > 0):
            return jsonify({
                'total_duration': duration_data['total_duration'].total_seconds() if duration_data['total_duration'] else 0,
                'worktime_duration': duration_data['worktime_duration'].total_seconds() if duration_data['worktime_duration'] else 0,
                'offhour_duration': duration_data['offhour_duration'].total_seconds() if duration_data['offhour_duration'] else 0,
                'internal_count': ip_counts['internal_count'],
                'external_count': ip_counts['external_count']
            })
        else:
            return jsonify({'error': 'No data found'}), 404
        
    except Exception as e:
        logging.error(f"예외 발생: {str(e)}, {traceback.format_exc()}")
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
            data = summary_service.get_top_user_duration_mixed(start_date, end_date, filter_is_deleted=True)
            logging.info(f"get_top_user_duration_mixed: {data}")
            
            if data['has_data']:
                response = {'data': data}
                return jsonify(response),200
            else:
                return jsonify({'error': 'No data found'}), 404        
            
        elif period_type in ['quarter', 'half', 'year']:            
            user_duration_map = {}

            all_user = db.session.query(Users.id, Users.name).filter(Users.is_deleted == False).all()
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
                data = summary_service.get_top_user_duration_mixed(start_date, end_date, filter_is_deleted=True)
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
            data = summary_service.get_top_department_duration_mixed(start_date, end_date, filter_is_deleted=True)
            logging.info(f"get_top_department_duration_mixed: {data}")
            
            if data['has_data']:
                response = {'data': data}
                return jsonify(response),200
            else:
                return jsonify({'error': 'No data found'}), 404
        elif period_type in ['quarter', 'half', 'year']:
            dept_duration_map = {}
            
            all_dept = db.session.query(Users.company, Users.department).filter(Users.is_deleted == False).all()
            for company, department in all_dept:
                dept_duration_map[(company, department)] = 0
                
            summary_rows = summary_service.get_summary_rows_agg(
                loginSummaryAgg,
                period_type = period_type,
                period_value = period_value,
                join_users=True,
                group_fields=[Users.company, Users.department]  # Users 테이블의 company, department 필드로 그룹화
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
                data = summary_service.get_top_department_duration_mixed(start_date, end_date, filter_is_deleted=True)

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
            data = summary_service.get_top_company_duration_mixed(start_date, end_date, filter_is_deleted=True)
            
            if data['has_data']:
                response = {'data': data}
                return jsonify(response),200
            else:                    
                return jsonify({'error': 'No data found'}), 404
        elif period_type in ['quarter', 'half', 'year']:
            company_duration_map = {}
            
            all_company = db.session.query(Users.company).filter(Users.is_deleted == False).distinct().all()
            for (company,) in all_company:
                company_duration_map[company] = 0
                
            summary_rows = summary_service.get_summary_rows_agg(
                loginSummaryAgg,
                period_type= period_type,
                period_value= period_value,
                join_users=True,
                group_fields=[Users.company]
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
                data = summary_service.get_top_company_duration_mixed(start_date, end_date, filter_is_deleted=True)
                
                if data['has_data']:
                    response = {'data': data}
                    return jsonify(response),200
                else:                    
                    return jsonify({'error': 'No data found'}), 404
            
    except Exception as e:
        logging.error(f"[get_top_company_duration] error: {str(e)}, {traceback.format_exc()}")
        return jsonify({'[get_top_company_duration] error': str(e)}), 500
    