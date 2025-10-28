from datetime import datetime, date, time, timezone
import logging
import log_config
import re
from flask_jwt_extended import jwt_required
from extensions import db
from models import ( Users, ContentViewingHistory, MemoData, ContentManager, 
                    ContentRelChannels, ContentRelFolders, ContentRelPages, ContentRelPageDetails, Assignees )
from sqlalchemy import func
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import aliased
import traceback
from utils.user_query_utils import get_user_ids_by_scope

def get_statistics_data(start_date, end_date, filter_type, filter_value):
    files = get_normal_files_width_category_names() 
    avgtimes = get_avg_learning_time_per_file(start_date, end_date, filter_type, filter_value)
    memocounts = get_memo_count_per_file(start_date, end_date, filter_type, filter_value)
    managers = get_folder_managers()
        
    if not files:
        logging.error("No files found")
        return None
    
    for f in files:
        f['avg_stay_duration'] = round(avgtimes.get(f['file_id'], 0), 1)
        f['memo_count'] = memocounts.get(f['file_id'], 0)
        f['manager_name'] = managers.get(f['mid_folder_id'], '')
        
    return files
                
def get_normal_files_width_category_names():
    """
    폴더 타입이 normal인 파일 목록에 카테고리 이름도 같이 가져오기(상세보기 제외)
    """
    try:                
        def clean_name(name):
            return re.sub(r'^\d+_|(\.[^./\\]+$)', '', name) if name else None
        
        Folders = aliased(ContentRelFolders)
        
        query = db.session.query(
            ContentRelPages.id, 
            ContentRelPages.name, 
            ContentRelPages.updated_at,
            ContentRelPages.folder_id,
            ContentRelChannels.id.label('top_folder_id'),
            ContentRelChannels.name.label('top_name')
        ).join(
            Folders, ContentRelPages.folder_id == Folders.id
        ).join(
            ContentRelChannels, Folders.channel_id == ContentRelChannels.id
        ).filter(
            ContentRelPages.is_deleted == False
        )
        
        # 전체 폴더를 가져와 dict로 구성
        all_folders = db.session.query(ContentRelFolders).all()
        folder_map = {f.id: f for f in all_folders}
        
        results = []
        for file_id,file_name,update_at,folder_id,top_folder_id,top_name in query.all():
            mid_folder = get_mid_folder_from_cache(folder_id, folder_map)           
            
            top_name_clean = clean_name(top_name)
            mid_name = clean_name(mid_folder.name) if mid_folder else ''
            if not mid_name:
                logging.warning(f"mid_name is empty for file_id: {file_id}, folder_id: {folder_id}, top_folder_id: {top_folder_id}")
            bottom_name = clean_name(file_name)
            
            sort_key = (top_name, mid_folder.name if mid_folder else '', file_name)
            
            result = {
                'file_id': file_id,
                'file_name': file_name,
                'folder_id': folder_id,
                'top_folder_id': top_folder_id,
                'top_name': top_name_clean,
                'mid_folder_id' : mid_folder.id if mid_folder else None,
                'mid_name': mid_name,
                'bottom_name': bottom_name,
                'update_at': update_at.strftime('%Y-%m-%d'),
                '_sort_key': sort_key
            }  
            results.append(result)
        
        results.sort(key=lambda x: (x['_sort_key']))
        return results
    except Exception as e:
        logging.error(f"[get_normal_files]: {str(e)}, {traceback.format_exc()}")
        return None

def get_mid_folder_from_cache(folder_id, folder_map):
    """
    folder_id에서 시작해 parent_id를 따라 올라가며 폴더를 찾는다.
    """
    while folder_id:
        folder = folder_map.get(folder_id)
        if folder is None:
            return None
        
        if folder.parent_id is None:
            return folder
        
        folder_id = folder.parent_id
    return None 

def get_avg_learning_time_per_file(start_dt, end_dt, scope, filter_value):
    """
    파일별 평균 학습 시간
    """
    user_ids = get_user_ids_by_scope(scope, filter_value) if scope != 'all' else None
    
    local_tz = datetime.now().astimezone().tzinfo
    if isinstance(start_dt, date) and not isinstance(start_dt, datetime):
        start_dt = datetime.combine(start_dt, time.min, tzinfo=local_tz).astimezone(timezone.utc)

    if isinstance(end_dt, date) and not isinstance(end_dt, datetime):
        end_dt = datetime.combine(end_dt, time.max, tzinfo=local_tz).astimezone(timezone.utc)

    dur_sec = func.extract('epoch', ContentViewingHistory.stay_duration)

    # 파일별 (총 학습시간) / (그 파일을 본 고유 사용자 수)
    avg_expr = (
        func.sum(dur_sec) / func.nullif(func.count(func.distinct(ContentViewingHistory.user_id)), 0)
    ).label('avg_sec')

    q = db.session.query(
        ContentViewingHistory.file_id,
        avg_expr
    ).filter(
        ContentViewingHistory.start_time >= start_dt,
        ContentViewingHistory.start_time <= end_dt
    )

    if user_ids:
        q = q.filter(ContentViewingHistory.user_id.in_(user_ids))

    q = q.group_by(ContentViewingHistory.file_id)

    return {r.file_id: round(float(r.avg_sec or 0), 1) for r in q.all()}

def get_memo_count_per_file(start_dt, end_dt, scope, filter_value):
    user_ids = get_user_ids_by_scope(scope, filter_value) if scope != 'all' else None
    
    query = db.session.query(
        MemoData.file_id,
        func.count(MemoData.id).label('memo_count')
    ).filter(
        MemoData.modified_at >= start_dt,
        MemoData.modified_at <= end_dt
    )
    
    if user_ids:
        query = query.filter(MemoData.user_id.in_(user_ids))
        
    query = query.group_by(MemoData.file_id)
    return {row.file_id: row.memo_count for row in query.all()}

def get_file_managers():
    """
    파일 관리자 목록 가져오기
    """
    query = db.session.query(
        ContentManager.file_id,
        Assignees.name.label('manager_name')
    ).join(
        Assignees, ContentManager.assignee_id == Assignees.id
    ).filter(ContentManager.type == 'file')
        
    return {row.file_id: row.manager_name for row in query.all()}

def get_folder_managers():
    """
    폴더 관리자 목록 가져오기
    """
    query = db.session.query(
        ContentManager.folder_id,
        Assignees.name.label('manager_name')
    ).join(
        Assignees, ContentManager.assignee_id == Assignees.id   
    ).filter(ContentManager.type == 'folder')
        
    return {row.folder_id: row.manager_name for row in query.all()}

def format_seconds_to_hhmmss(seconds):
    """
    초를 시:분:초 형식으로 변환
    """
    if seconds is None:
        return '00시간 00분 00초'
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    
    return f"{hours:02}시간 {minutes:02}분 {seconds:02}초"