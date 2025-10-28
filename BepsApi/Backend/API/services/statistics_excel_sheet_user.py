from datetime import datetime, time, timezone
import logging
import log_config
from sqlalchemy import func
from sqlalchemy.orm import aliased
from extensions import db
import re
from models import (Users, ContentViewingHistory,
                    ContentRelPages, ContentRelChannels, ContentRelFolders, ContentRelPageDetails,
                    MemoData)

def get_statistics_user_data(period_type, period_value, filter_value):
    from services.user_summary_service import get_period_value
    
    start_dt, end_dt = get_period_value(period_type, period_value)
    local_tz = datetime.now().astimezone().tzinfo
    utc_start_dt = datetime.combine(start_dt, time.min, tzinfo=local_tz).astimezone(timezone.utc)
    utc_end_dt = datetime.combine(end_dt, time.max, tzinfo=local_tz).astimezone(timezone.utc)    
    
    CVH = aliased(ContentViewingHistory)
    Folder = aliased(ContentRelFolders)
    Page = aliased(ContentRelPages)
    Detail = aliased(ContentRelPageDetails)

    # file_type이 detail인 것만 필터링
    subq_detail = db.session.query(
        ContentViewingHistory.file_id,
        func.max(ContentViewingHistory.start_time).label('latest_time')
        ).filter(
            ContentViewingHistory.user_id == filter_value,
            ContentViewingHistory.file_type == 'detail',
            ContentViewingHistory.start_time >= utc_start_dt,
            ContentViewingHistory.start_time <= utc_end_dt
        ).group_by(
            ContentViewingHistory.file_id
        ).subquery()
        
    query_dtail = db.session.query(
        Users.company,
        Users.department,
        Users.id.label('user_id'),
        Users.name.label('user_name'),
        ContentRelChannels.name.label('channel_name'),
        Folder.name.label('folder_name'),
        Page.name.label('file_name'),
        Detail.name.label('detail_name'),
        CVH.start_time,
        CVH.end_time,
        CVH.stay_duration,
        CVH.ip_address
    ).join(
        CVH, CVH.user_id == Users.id
    ).join(
        subq_detail, (CVH.file_id == subq_detail.c.file_id) & 
                     (CVH.start_time == subq_detail.c.latest_time)
    ).join(
        Detail, CVH.file_id == Detail.id
    ).join(
        Page, Detail.page_id == Page.id
    ).join(
        Folder, Page.folder_id == Folder.id
    ).join(
        ContentRelChannels, Folder.channel_id == ContentRelChannels.id
    ).filter(
        Folder.parent_id == None,
        Users.id == filter_value
    ).group_by(
        Users.company,
        Users.department,
        Users.id,
        Users.name,
        ContentRelChannels.name,
        Folder.name,
        Page.name,
        Detail.name,
        CVH.start_time,
        CVH.end_time,
        CVH.stay_duration,
        CVH.ip_address
    ).all()


    # file_type이 page인 것만 필터링
    # 최신 조회기록만 고르기 위한 서브쿼리
    subq = db.session.query(
        ContentViewingHistory.file_id,
        func.max(ContentViewingHistory.start_time).label('latest_time')
    ).filter(
        ContentViewingHistory.user_id == filter_value,
        ContentViewingHistory.file_type == 'page',
        ContentViewingHistory.start_time >= utc_start_dt,
        ContentViewingHistory.start_time < utc_end_dt
    ).group_by(
        ContentViewingHistory.file_id
    ).subquery()
    
    # 원본 테이블에서 해당 기록만 가져오기
    query = db.session.query(
        Users.company,
        Users.department,
        Users.id.label('user_id'),
        Users.name.label('user_name'),
        ContentRelChannels.name.label('channel_name'),
        Folder.name.label('folder_name'),
        ContentRelPages.name.label('file_name'),
        func.count(MemoData.id).label('memo_count'),
        CVH.start_time,
        CVH.end_time,
        CVH.stay_duration,
        CVH.ip_address
        ).join(
            CVH, CVH.user_id == Users.id
        ).join(
            subq, (CVH.file_id == subq.c.file_id) & 
                  (CVH.start_time == subq.c.latest_time)
        ).join(
            ContentRelPages, CVH.file_id == ContentRelPages.id
        ).join(
            Folder, ContentRelPages.folder_id == Folder.id
        ).join(
            ContentRelChannels, Folder.channel_id == ContentRelChannels.id
        ).outerjoin(
            MemoData, (ContentRelPages.id == MemoData.file_id) & 
                      (MemoData.user_id == Users.id) &
                      (MemoData.modified_at >= utc_start_dt) & 
                      (MemoData.modified_at <= utc_end_dt)
        ).filter(
            Folder.parent_id == None,
            Users.id == filter_value
        ).group_by(
            Users.company,
            Users.department,
            Users.id,
            Users.name,
            ContentRelChannels.name,
            Folder.name,
            ContentRelPages.name,
            CVH.start_time,
            CVH.end_time,
            CVH.stay_duration,
            CVH.ip_address
        ).all()
    
    page_rows = [row_to_dict(row, 'page', local_tz) for row in query]
    detail_rows = [row_to_dict(row, 'detail', local_tz) for row in query_dtail]
    
    query_combined = page_rows + detail_rows
    query_combined.sort(key=lambda x: (
        x.get('channel_name') or '',
        x.get('folder_name') or '',
        x.get('file_name') or '',
        x.get('detail_name') or ''
    ))
    # query_combined.sort(key=lambda x: (x['channel_name'], x['folder_name'], x['file_name'], x['detail_name']))
    
    return query_combined

def row_to_dict(row, file_type, local_tz):
    channel = re.sub(r'^\d+_', '', row.channel_name)
    folder = re.sub(r'^\d+_', '', row.folder_name)
    filename = re.sub(r'^\d+_|(\.[^./\\]+$)', '', row.file_name)
    return {
        'company': row.company,
        'department': row.department,
        'user_id': row.user_id,
        'user_name': row.user_name,
        'channel_name': row.channel_name,
        'folder_name': row.folder_name,
        'file_name': row.file_name,
        'detail_name': row.detail_name if file_type == 'detail' else None,
        'full_name': f"{channel} - {folder} - {filename}",
        'memo_count': row.memo_count if file_type == 'page' else 0,
        'start_time': row.start_time.astimezone(local_tz).strftime('%Y-%m-%d %H:%M:%S'),
        'end_time': row.end_time.astimezone(local_tz).strftime('%Y-%m-%d %H:%M:%S'),
        'stay_duration': format_timedelta_to_minsec(row.stay_duration),
        'ip_address': row.ip_address
    }

def format_timedelta_to_minsec(td):
    """
    timedelta 객체를 분:초 형식의 문자열로 변환합니다.
    """
    total_seconds = int(td.total_seconds())
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02}분{seconds:02}초"