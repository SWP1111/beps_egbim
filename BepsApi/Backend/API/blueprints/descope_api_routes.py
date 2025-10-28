import logging
import os
import log_config
from flask import Blueprint, request
from flask_jwt_extended import jwt_required
import requests
from flasgger import swag_from

api_descope_bp = Blueprint('descope', __name__)

@api_descope_bp.route('/get_user_info', methods=['GET'])
@swag_from(os.path.join(os.path.dirname(__file__), '..', 'docs', 'descope_api.yaml'))
def get_user_info():
    """
    Descope 사용자 정보 조회 API
    """
    try:
        logging.debug("Received headers: %s", request.headers)
        refresh_token = request.headers.get('X-Descope-Refresh-Token')
        if not refresh_token:
            return {'error': 'refresh_token is required'}, 400
        
        headers = {
            'Authorization': f'Bearer P2wON5fy1K6kyia269VpeIzYP8oP:{refresh_token}',
        }
        
        response = requests.get('https://api.descope.com/v1/auth/me', headers=headers)
        if response.status_code != 200:
            return {'error': 'Failed to retrieve user info from Descope'}, response.status_code
        
        return response.json(), 200
    except Exception as e:
        return {'error': str(e)}, 500
    