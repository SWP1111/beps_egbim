from datetime import datetime
import logging
import log_config
import os
import uuid
from flask import Blueprint, request, jsonify, send_file, send_from_directory
from services.statistics_excel_service import export_statistics_to_excel
from config import Config

api_statistics_bp = Blueprint('statistics', __name__)   # 블루프린트 생성

@api_statistics_bp.route('/preview', methods=['GET'])
def preview_statistics():
    from services.user_summary_service import get_period_value
    """
    엑셀 미리보기
    """
    period_value = request.args.get('period_value')
    period_type = request.args.get('period_type')
    filter_type = request.args.get('filter_type')
    filter_value = request.args.get('filter_value')
    
    local_tz = datetime.now().astimezone().tzinfo
    local_tz_name = local_tz.tzname(None)
    if local_tz_name == 'KST':
        local_tz_name = 'Asia/Seoul'
            
    # start_date, end_date = get_period_value(period_type, period_value)
    filename = str(uuid.uuid4()) 
    result = export_statistics_to_excel(Config.UPLOAD_DIR, filename, period_type, period_value, filter_type, filter_value)  # 엑셀 파일 생성
    return jsonify({
        'filename': result['excel_path'],
        'content_html_name': f"statistics/preview/html/{result['html_content_name']}",
        'org_html_name': f"statistics/preview/html/{result['html_org_name']}",
        'user_html_name': f"statistics/preview/html/{result['html_user_name']}" if result['html_user_name'] is not None else None,
        'timezone': local_tz_name
    })
    
@api_statistics_bp.route('/preview/html/<path:filename>', methods=['GET'])
def preview_html(filename):
    return send_from_directory(Config.UPLOAD_DIR, filename)
  
@api_statistics_bp.route('/preview/html_segment', methods=['GET'])
def preview_html_segment():
    """
    HTML 행 단위 분할 미리보기 API
    GET params:
        - filename: HTML 파일명
        - page: 페이지 번호
        - per_page: 최대 행 수 (기본 500)
    """
    import re
    from flask import Response

    filename = request.args.get('filename')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 500))

    full_path = os.path.join(Config.UPLOAD_DIR, filename)
    if not os.path.exists(full_path):
        return jsonify({'error': 'HTML 파일이 존재하지 않습니다.'}), 404

    with open(full_path, 'r', encoding='utf-8') as f:
        html = f.read()

    style_match = re.search(r'<style.*?>.*?</style>', html, flags=re.DOTALL)
    style = style_match.group(0) if style_match else ''

    thead_match = re.search(r'<thead.*?>.*?</thead>', html, flags=re.DOTALL)
    thead = thead_match.group(0) if thead_match else ''

    rows = re.findall(r'<tr.*?>.*?</tr>', html, flags=re.DOTALL)

    # 그룹 기준: 대분류/중분류/소분류 등으로 연속된 그룹 자르기
    blocks = []
    current_block = []
    row_count = 0

    for row in rows:
        current_block.append(row)
        row_count += 1
        if row_count >= per_page:
            blocks.append(current_block)
            current_block = []
            row_count = 0

    if current_block:
        blocks.append(current_block)

    if page > len(blocks) or page < 1:
        return jsonify({'error': '페이지 범위를 벗어났습니다.'}), 400

    selected_rows = blocks[page - 1]
    thread_html = thead if page != 1 else ''
    html_response = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset='utf-8'>
        {style}
    </head>
    <body>
        <table>
            {thread_html}
            <tbody>
                {''.join(selected_rows)}
            </tbody>
        </table>
    </body>
    </html>
    """
    
    return jsonify({
        'html' : html_response,
        'total_page': len(blocks)
    })


@api_statistics_bp.route('/download', methods=['GET'])
def download_statistics():
    """
    엑셀 다운로드
    """
    file_path = request.args.get('file_path')
    download_name = request.args.get('download_name')
    
    if not os.path.exists(file_path):
        return jsonify({
            'error': 'File not found'
        }), 404
        
    resposne = send_file(file_path, download_name=f"beps_{download_name}.xlsx", as_attachment=True)
    #os.remove(file_path)  # 다운로드 후 파일 삭제
    return resposne
