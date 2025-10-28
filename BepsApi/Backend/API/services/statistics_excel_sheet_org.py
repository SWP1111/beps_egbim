from collections import defaultdict
from datetime import datetime, time, timezone
import logging
from sqlalchemy import text
import log_config
from extensions import db
from models import Users
import re

def get_statistics_org_data(period_type, period_value, filter_type, filter_value):
    """
    통계 데이터를 가져오는 함수
    """
    users, user_count = get_users_for_export(filter_type, filter_value)

    results = []
    user_ids = [
        user['user_id'] for department in users.values() for user_list in department.values() for user in user_list
    ]
    total_learning_time_by_users = get_total_learning_time_by_users(user_ids, period_type, period_value)
    memo_count_per_category_by_users = get_memo_count_per_category_by_users(user_ids, period_type, period_value)
    
    base_row = {
    'company': '',
    'department': '',
    'user_id': '',
    'name': '',
    'total_learning_time': '',
    'avg_learning_time': '',
    'category_name': '',
    'learning_time': '',
    'memo_count': 0,
    'total_learning_time_sec': 0,
    'learning_time_sec': 0,
    'count': 1
    }
    
    for company, departments in users.items():
        if filter_type in ('all', 'company'):
            user_list = [user['user_id'] for department_user_list in departments.values()
                         for user in department_user_list]
            channel_duration_map,channel_memo_map = config_channel_memo_map(user_list, total_learning_time_by_users, memo_count_per_category_by_users)              
            company_row = base_row.copy()
            company_row['company'] = company
            
            company_rows = config_rows(company_row, channel_duration_map, channel_memo_map, len(user_list))
            results.extend(company_rows)
        
        for department, users in departments.items():
            if filter_type in ('all', 'company', 'department'):
                user_list = [user['user_id'] for user in users]
                channel_duration_map,channel_memo_map = config_channel_memo_map(user_list, total_learning_time_by_users, memo_count_per_category_by_users)              
                department_row = base_row.copy()
                department_row['company'] = company
                department_row['department'] = department
                
                department_rows = config_rows(department_row, channel_duration_map, channel_memo_map, len(user_list))
                results.extend(department_rows)
            
            for user in users:
                user_id = user['user_id']
                channel_duration_map,channel_memo_map = config_channel_memo_map([user_id], total_learning_time_by_users, memo_count_per_category_by_users)              
                user_row = base_row.copy()
                user_row['company'] = company
                user_row['department'] = department
                user_row['user_id'] = user_id
                user_row['name'] = user['name']
                
                user_rows = config_rows(user_row, channel_duration_map, channel_memo_map, 1)
                results.extend(user_rows)
                            
    return results

def get_users_for_export(filter_type, filter_value):
    """
    사용자 목록을 가져오는 함수
    """
    qeury = db.session.query(
        Users.company,
        Users.department,
        Users.name,
        Users.id).filter(Users.is_deleted == False)
    
    if filter_type == 'company':
        qeury = qeury.filter(Users.company == filter_value)
    elif filter_type == 'department':
        parts = filter_value.split('||', 1)
        if len(parts) == 2:
            qeury = qeury.filter(Users.company == parts[0], Users.department == parts[1])
        else:
            qeury = qeury.filter(Users.department == parts[0])
    elif filter_type == 'user':
        qeury = qeury.filter(Users.id == filter_value)
        
    rows = qeury.order_by(Users.company, Users.department, Users.name).all()
    
    results = {}
    for row in rows:
        company = row.company
        department = row.department
        user_id = row.id
        name = row.name
        if company not in results:
            results[company] = {}
            
        if department not in results[company]:
            results[company][department] = []
            
        results[company][department].append({
            "user_id": user_id,
            "name": name,
        })
                                            
    return results, len(rows)

def get_total_learning_time(period_type, period_value, filter_type, filter_value, user_count):
    """
    총 학습 시간을 가져오는 함수
    """
    from services.leaning_summary_service import get_folder_progress
    
    params = {
        'period_type': period_type,
        'period_value': period_value,
        'filter_type': filter_type,
        'filter_value': filter_value
    }
    folder_progress = get_folder_progress(params)
    sorted_folder_progress = sorted(folder_progress.values(), key=lambda x: x[0])
    total_learning_time = sum(duration.total_seconds() for folder_name, duration in folder_progress.values())
    
    if user_count == 0: user_count = 1
    avg_learning_time = total_learning_time / user_count
    
    return {
        'total_learning_time': f"{int(total_learning_time // 3600):02}시간{int((total_learning_time % 3600) // 60):02}분{int(total_learning_time % 60):02}초" ,
        'avg_learning_time': f"{int(avg_learning_time // 3600):02}시간{int((avg_learning_time % 3600) // 60):02}분{int(avg_learning_time % 60):02}초",
        'folder_progress': sorted_folder_progress
    }

def get_total_learning_time_by_users(user_ids, period_type, period_value):
    """
    사용자별 총 학습 시간을 가져오는 함수
    """
    from services.leaning_summary_service import get_folder_progress_by_users

    folder_progress_by_users = get_folder_progress_by_users(user_ids=user_ids, period_type=period_type, period_value=period_value) 
    
    sorted_folder_progress_by_users = {}
    for user_id, channel_data  in folder_progress_by_users.items():
        sorted_folder_progress_by_users[user_id] = sorted(channel_data.values(), key=lambda x: x[0])
    return folder_progress_by_users

def get_memo_count_per_category(period_type, period_value, filter_type, filter_value):
    """
    카테고리별 메모 수를 가져오는 함수
    """    
    from services.user_summary_service import get_period_value
    
    start_dt, end_dt = get_period_value(period_type, period_value)
    local_tz = datetime.now().astimezone().tzinfo
    utc_start_dt = datetime.combine(start_dt, time.min, tzinfo=local_tz).astimezone(timezone.utc)
    utc_end_dt = datetime.combine(end_dt, time.max, tzinfo=local_tz).astimezone(timezone.utc)    
    
    base_query = """
        SELECT c.id AS channel_id, c.name AS channel_name, COUNT(*) AS memo_count
        FROM memos m
        JOIN content_rel_folders f ON m.folder_id = f.id
        JOIN content_rel_channels c ON f.channel_id = c.id
        JOIN users u ON m.user_id = u.id
        WHERE {user_filter}
            AND m.modified_at >= :start_dt
            AND m.modified_at <= :end_dt
        GROUP BY c.id, c.name
        ORDER BY fc.folder_name
    """
    
    params = {
        'start_dt': utc_start_dt,
        'end_dt': utc_end_dt
    }
    user_filter = '1=1'
    
    if filter_type == 'company':
        user_filter = 'u.company = :company'
        params['company'] = filter_value
    elif filter_type == 'department':
        user_filter = 'u.company = :company AND u.department = :department'
        parts = filter_value.split('||', 1)
        if len(parts) == 2:
            params['company'] = parts[0]
            params['department'] = parts[1]
        else:
            user_filter = 'u.department = :department'
            params['department'] = parts[0]
    elif filter_type == 'user':
        user_filter = 'u.id = :user_id'
        params['user_id'] = filter_value
      
    query = text(base_query.format(user_filter=user_filter)) 
    result = db.session.execute(query, params).mappings().all()

    data = [{
        'channel_id': row['channel_id'],
        'channel_name': row['channel_name'],
        'memo_count': row['memo_count']
    } for row in result]
    
    return data

def get_memo_count_per_category_by_users(user_ids, period_type, period_value):
    """
    여러 사용자의 카테고리별 메모 수를 가져오는 함수
    """
    from services.user_summary_service import get_period_value
    
    start_dt, end_dt = get_period_value(period_type, period_value)
    local_tz = datetime.now().astimezone().tzinfo
    utc_start_dt = datetime.combine(start_dt, time.min, tzinfo=local_tz).astimezone(timezone.utc)
    utc_end_dt = datetime.combine(end_dt, time.max, tzinfo=local_tz).astimezone(timezone.utc)    
    
    base_query = """
        SELECT u.id AS user_id, c.id AS channel_id, c.name AS channel_name, COUNT(*) AS memo_count
        FROM memos m
        JOIN content_rel_pages p ON m.file_id = p.id
        JOIN content_rel_folders f ON p.folder_id = f.id
        JOIN content_rel_channels c ON f.channel_id = c.id
        JOIN users u ON m.user_id = u.id
        WHERE m.user_id = ANY(:user_ids)
            AND m.modified_at >= :start_dt
            AND m.modified_at <= :end_dt
        GROUP BY u.id, c.id, c.name
        ORDER BY c.name
    """
    
    params = {
        'start_dt': utc_start_dt,
        'end_dt': utc_end_dt,
        'user_ids': user_ids
    }
    
    query = text(base_query) 
    result = db.session.execute(query, params).mappings().all()

    memo_counts = defaultdict(dict)
    for row in result:
        memo_counts[row['user_id']][row['channel_id']] = {
            'channel_name': row['channel_name'],
            'memo_count': row['memo_count']
        }
    
    return memo_counts

def config_channel_memo_map(user_list,total_learning_time_by_users, memo_count_per_category_by_users):
    """
    채널 맵을 설정하는 함수
    """
    channel_duration_map = {}
    channel_memo_map = {}
    for uid in user_list:
        user_channels = total_learning_time_by_users.get(uid, {})
        user_memo = memo_count_per_category_by_users.get(uid, {})
        for channel_id, (channel_name, duration) in user_channels.items():
            prev = channel_duration_map.get(channel_id)
            if prev is None:
                channel_duration_map[channel_id] = (channel_name, duration)
            else:
                channel_duration_map[channel_id] = (prev[0], prev[1] + duration)
        for channel_id, memo_info in user_memo.items():
            prev = channel_memo_map.get(channel_id)
            memo_count = memo_info.get('memo_count', 0)
            if prev is None:
                channel_memo_map[channel_id] = (channel_name, memo_count)
            else:
                channel_memo_map[channel_id] = (prev[0], prev[1] + memo_count)
    
    return channel_duration_map, channel_memo_map

def config_rows(base_row, channel_duration_map, channel_memo_map, user_count):
    """
    채널 맵을 설정하는 함수
    """
    
    total_learning_time = 0
    rows = []
    for channel_id, (channel_name, duration) in channel_duration_map.items():
       row = base_row.copy()
       row['category_name'] = re.sub(r"^\d+_", "", channel_name)
       seconds = duration.total_seconds()
       total_learning_time += seconds
       row['learning_time'] = f"{int(seconds // 3600):02}시간{int((seconds % 3600) // 60):02}분{int(seconds % 60):02}초"
       row['learning_time_sec'] = seconds
       row['memo_count'] = channel_memo_map.get(channel_id, {})[1] if channel_memo_map.get(channel_id) else 0
       row['total_learning_time_sec'] = total_learning_time
       rows.append(row)

    if rows:
        total_str = f"{int(total_learning_time // 3600):02}시간{int((total_learning_time % 3600) // 60):02}분{int(total_learning_time % 60):02}초" 
        avg_sec = total_learning_time / user_count
        avg_str = f"{int(avg_sec // 3600):02}시간{int((avg_sec % 3600) // 60):02}분{int(avg_sec % 60):02}초"
        rows[0]['total_learning_time'] = total_str
        rows[0]['avg_learning_time'] = avg_str
        
    return rows