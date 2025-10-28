import ipaddress
import logging
import log_config
import datetime
from extensions import db
from models import LoginHistory, loginSummaryDay, loginSummaryAgg, Users, IpRange
from collections import defaultdict
from sqlalchemy import case, func, cast, or_, false
import config
from services.ip_range_cache import ip_range_list
from sqlalchemy.dialects.postgresql import INET

def get_quarter_period_value(year):
    """주어진 연도에 대한 분기 기간을 반환합니다."""
    return [
        ("{}-Q1".format(year), datetime.date(year, 1, 1), datetime.date(year, 3, 31)),
        ("{}-Q2".format(year), datetime.date(year, 4, 1), datetime.date(year, 6, 30)),
        ("{}-Q3".format(year), datetime.date(year, 7, 1), datetime.date(year, 9, 30)),
        ("{}-Q4".format(year), datetime.date(year, 10, 1), datetime.date(year, 12, 31))
    ]
    
def get_half_period_value(year):
    """주어진 연도에 대한 반기 기간을 반환합니다."""
    return [
        ("{}-H1".format(year), datetime.date(year, 1, 1), datetime.date(year, 6, 30)),
        ("{}-H2".format(year), datetime.date(year, 7, 1), datetime.date(year, 12, 31))
    ]

def get_year_period_value(year):
    """주어진 연도에 대한 연도 기간을 반환합니다."""
    return [
        ("{}".format(year), datetime.date(year, 1, 1), datetime.date(year, 12, 31))
    ]

def is_range_used(start, end, used_ranges):
    """주어진 범위가 이미 사용된 범위에 포함되는지 확인합니다."""
    for u_start, u_end in used_ranges:
        if start >= u_start and end <= u_end:
            return True
    return False

def get_period_value(period_type: str, period_value: str):
    """
    주어진 기간 유형과 값에 따라 시작일과 종료일을 반환합니다.
    period_type: 'year', 'half', 'quarter'
    period_value:
        - year: '2025'
        - half: '2025-H1', '2025-H2'
        - quarter: '2025-Q1', '2025-Q2', '2025-Q3', '2025-Q4'
    """
    if period_type == 'year':
        year = int(period_value)
        return datetime.date(year, 1, 1), datetime.date(year, 12, 31)

    elif period_type == 'half':
        year, half = period_value.split('-H')
        year = int(year)
        half = int(half)
        if half == 1:
            return datetime.date(year, 1, 1), datetime.date(year, 6, 30)
        elif half == 2:
            return datetime.date(year, 7, 1), datetime.date(year, 12, 31)
        else:
            raise ValueError(f"Invalid half value: {period_value}")

    elif period_type == 'quarter':
        year, quarter = period_value.split('-Q')
        year = int(year)
        quarter = int(quarter)
        if quarter == 1:
            return datetime.date(year, 1, 1), datetime.date(year, 3, 31)
        elif quarter == 2:
            return datetime.date(year, 4, 1), datetime.date(year, 6, 30)
        elif quarter == 3:
            return datetime.date(year, 7, 1), datetime.date(year, 9, 30)
        elif quarter == 4:
            return datetime.date(year, 10, 1), datetime.date(year, 12, 31)
        else:
            raise ValueError(f"Invalid quarter value: {period_value}")

    elif period_type == 'day':
        start_str, end_str = period_value.split('~')
        start_date = datetime.datetime.strptime(start_str.strip(), '%Y-%m-%d').date()
        end_date = datetime.datetime.strptime(end_str.strip(), '%Y-%m-%d').date()
        return start_date, end_date
    
    else:
        raise ValueError(f"Invalid period_type: {period_type}")

def get_top_user_duration_mixed(start_date, end_date, filter_is_deleted = False):
    """주어진 기간 동안의 사용자별 총 로그인 시간 중 제일 높은 시간 정보를 반환합니다."""
    user_duration_map = {}
    used_ranges = []

    all_users = db.session.query(Users.id, Users.name)
    if filter_is_deleted:
        all_users = all_users.filter(Users.is_deleted == False)
    all_users = all_users.all()
    
    for user in all_users:
        user_duration_map[user.id.lower()] = (user.name, 0)
    
    def update_user_duration(rows, user_id_fields='user_id'):
        for row in rows:
            user_id = getattr(row, user_id_fields, None)
            if user_id:
                prev = user_duration_map.get(user_id.lower())
                duration = (row.total.total_seconds() if row.total else 0)
                if prev:
                    user_duration_map[user_id.lower()] = (prev[0], prev[1] + duration)
                else:
                    user_duration_map[user_id.lower()] = (row.name, duration)                
    
    for period_func, summary_func, period_type in [
        (get_year_period_value, loginSummaryAgg, 'year'),
        (get_half_period_value, loginSummaryAgg, 'half'),
        (get_quarter_period_value, loginSummaryAgg, 'quarter')
    ]:
        for period_str, p_start, p_end in period_func(start_date.year):
            if start_date <= p_start and end_date >= p_end and not is_range_used(p_start, p_end, used_ranges):
                summary_rows = get_summary_rows_agg(
                    summary_func,
                    period_type=period_type,
                    period_value=period_str,
                    join_users=True,
                    group_fields=[loginSummaryAgg.user_id, Users.name]
                )
                if summary_rows:
                    used_ranges.append((p_start, p_end))
                    update_user_duration(summary_rows)
    
    used_ranges.sort(key=lambda x: x[0])
    current = start_date
    
    for used_start, used_end in used_ranges:
        if current < used_start: 
            current_end = used_start - datetime.timedelta(days=1)
            if current <= current_end:
                if current < (datetime.date.today() - datetime.timedelta(days=1)):     
                    try:
                        summary_day_rows = get_summary_rows_day(
                            loginSummaryDay,
                            start_date=current,
                            end_date=min(current_end, datetime.date.today() - datetime.timedelta(days=2)),
                            group_fields=[loginSummaryDay.user_id_key, Users.name],
                            join_users=True
                        )                                        
                        update_user_duration(summary_day_rows, user_id_fields='user_id_key')
                                             
                    except Exception as e:
                        logging.error(f"Error in summary_day_rows query: {e}")
                        return {
                            'has_data': False,
                            'user_id': None,
                            'duration': 0
                        }
                            
                elif used_start - datetime.timedelta(days=1) in (datetime.date.today(), datetime.date.today() - datetime.timedelta(days=1)):
                    local_tz = datetime.datetime.now().astimezone().tzinfo
                    utc_start_dt = datetime.datetime.combine(current, datetime.time.min, tzinfo=local_tz).astimezone(datetime.timezone.utc)
                    utc_end_dt = datetime.datetime.combine(used_start - datetime.timedelta(days=1), datetime.time.max, tzinfo=local_tz).astimezone(datetime.timezone.utc)
                    login_history_rows = get_summary_rows_history(
                        LoginHistory,
                        start_date=utc_start_dt,
                        end_date=utc_end_dt,
                        group_fields=[LoginHistory.user_id, Users.name]
                    )
                    update_user_duration(login_history_rows)                               
        current = max(current, used_end + datetime.timedelta(days=1))
                   
    if current <= end_date:
        if current < (datetime.date.today() - datetime.timedelta(days=1)):
            summary_day_rows = get_summary_rows_day(
                loginSummaryDay,
                start_date=current,
                end_date=min(end_date, datetime.date.today() - datetime.timedelta(days=2)),
                group_fields=[loginSummaryDay.user_id_key, Users.name],
                join_users=True
            )          
            update_user_duration(summary_day_rows, user_id_fields='user_id_key')            
        if end_date in (datetime.date.today(), datetime.date.today() - datetime.timedelta(days=1)):
            local_tz = datetime.datetime.now().astimezone().tzinfo
            utc_start_dt = datetime.datetime.combine(max(current, datetime.date.today() - datetime.timedelta(days=1)), datetime.time.min, tzinfo=local_tz).astimezone(datetime.timezone.utc)
            utc_end_dt = datetime.datetime.combine(end_date, datetime.time.max, tzinfo=local_tz).astimezone(datetime.timezone.utc)
            login_history_rows = get_summary_rows_history(
                LoginHistory,
                start_date=utc_start_dt,
                end_date=utc_end_dt,
                group_fields=[LoginHistory.user_id, Users.name]
            )         
            update_user_duration(login_history_rows)
    
    if user_duration_map:
        sorted_users = sorted(user_duration_map.items(), key=lambda x: x[1][1], reverse=True)
        sorted_users_by_low = sorted(user_duration_map.items(), key=lambda x: x[1][1])
        return {
            'has_data': True,
            'top':  [(user_id, name, duration) for user_id, (name, duration) in sorted_users[:3]],
            'bottom': [(user_id, name, duration) for user_id, (name, duration) in sorted_users_by_low[:3]],
        }
    else:
        return {
            'has_data': False,
            'user_id': None,
            'duration': 0
        }

def get_top_department_duration_mixed(start_date, end_date, filter_is_deleted = False):
    dept_duration_map = {}
    used_ranges = []
    
    all_departments = db.session.query(Users.company, Users.department).distinct()
    if filter_is_deleted:
        all_departments = all_departments.filter(Users.is_deleted == False)
    all_departments = all_departments.all()
    
    for company, department in all_departments:
        dept_duration_map[(company, department)] = 0
    
    def update_dept_duration(rows, company_filed='company', department_field='department'):
        for row in rows:
            key = (getattr(row, company_filed, None), getattr(row, department_field, None))
            if key not in dept_duration_map:
                dept_duration_map[key] = 0
            dept_duration_map[key] += (row.total.total_seconds() if row.total else 0)
        
    for period_func, summary_func, period_type in [
        (get_year_period_value, loginSummaryAgg, 'year'),
        (get_half_period_value, loginSummaryAgg, 'half'),
        (get_quarter_period_value, loginSummaryAgg, 'quarter')
    ]:
        for period_str, p_start, p_end in period_func(start_date.year):
            if start_date <= p_start and end_date >= p_end and not is_range_used(p_start, p_end, used_ranges):
                summary_rows = get_summary_rows_agg(
                    summary_func,
                    period_type=period_type,
                    period_value=period_str,
                    join_users=True,
                    group_fields=[Users.company, Users.department]
                )
                if summary_rows:
                    used_ranges.append((p_start, p_end))
                    update_dept_duration(summary_rows, company_filed='company', department_field='department')
                    
    used_ranges.sort(key=lambda x: x[0])
    current = start_date
                    
    for used_start, used_end in used_ranges:
        if current < used_start:
            current_end = used_start - datetime.timedelta(days=1)
            if current <= current_end:
                if current < (datetime.date.today() - datetime.timedelta(days=1)):
                    try:
                        rows = get_summary_rows_day(
                            loginSummaryDay,
                            start_date=current,
                            end_date=min(current_end, datetime.date.today() - datetime.timedelta(days=2)),
                            join_users=True,
                            group_fields=[Users.company, Users.department]
                        )
                        update_dept_duration(rows, company_filed='company', department_field='department')

                    except Exception as e:
                        logging.error(f"Error in summary_day_rows query: {e}")
                        return {
                            'has_data': False,
                            'company': None,
                            'department': None,
                            'duration': 0
                        }
                            
                if current_end >= datetime.date.today() - datetime.timedelta(days=1):
                    local_tz = datetime.datetime.now().astimezone().tzinfo
                    utc_start_dt = datetime.datetime.combine(current, datetime.time.min, tzinfo=local_tz).astimezone(datetime.timezone.utc)
                    utc_end_dt = datetime.datetime.combine(used_start - datetime.timedelta(days=1), datetime.time.max, tzinfo=local_tz).astimezone(datetime.timezone.utc)
                    rows = get_summary_rows_history(
                        LoginHistory,
                        start_date=utc_start_dt,
                        end_date=utc_end_dt,
                        group_fields=[Users.company, Users.department],
                    )
                    update_dept_duration(rows, company_filed='company', department_field='department')
       
        current = max(current, used_end + datetime.timedelta(days=1))
        
    if current <= end_date:
        if current < (datetime.date.today() - datetime.timedelta(days=1)):
            rows = get_summary_rows_day(
                loginSummaryDay,
                start_date=current,
                end_date=min(end_date, datetime.date.today() - datetime.timedelta(days=2)),
                join_users=True,
                group_fields=[Users.company, Users.department]
            )
            update_dept_duration(rows, company_filed='company', department_field='department')
        if end_date >= datetime.date.today() - datetime.timedelta(days=1):
            local_tz = datetime.datetime.now().astimezone().tzinfo
            utc_start_dt = datetime.datetime.combine(max(current, datetime.date.today() - datetime.timedelta(days=1)), datetime.time.min, tzinfo=local_tz).astimezone(datetime.timezone.utc)
            utc_end_dt = datetime.datetime.combine(end_date, datetime.time.max, tzinfo=local_tz).astimezone(datetime.timezone.utc)
            rows = get_summary_rows_history(
                LoginHistory,
                start_date=utc_start_dt,
                end_date=utc_end_dt,
                group_fields=[Users.company, Users.department],
            )
            update_dept_duration(rows, company_filed='company', department_field='department')
                
    if dept_duration_map:
        sorted_departments = sorted(dept_duration_map.items(), key=lambda x: x[1], reverse=True)
        sorted_departments_by_low = sorted(dept_duration_map.items(), key=lambda x: x[1])
        return {
            'has_data': True,
            'top': [(company, department, duration) for (company, department), duration in sorted_departments[:3]],
            'bottom': [(company, department, duration) for (company, department), duration in sorted_departments_by_low[:3]],
        }
    else:
        return {
            'has_data': False,
            'company': None,
            'department': None,
            'duration': 0
        }

def get_top_company_duration_mixed(start_date, end_date, filter_is_deleted = False):
    company_duaration_map = {}
    used_ranges = []
    
    all_companies = db.session.query(Users.company)
    if filter_is_deleted:
        all_companies = all_companies.filter(Users.is_deleted == False)
    all_companies = all_companies.distinct().all()
    
    for (company,) in all_companies:
        company_duaration_map[company] = 0
    
    def update_company_duration(rows, company_field='company'):
        for row in rows:
            company = getattr(row, company_field, None)
            if company not in company_duaration_map:
                company_duaration_map[company] = 0
            company_duaration_map[company] += (row.total.total_seconds() if row.total else 0)
    
    for period_func, summary_func, period_type in [
        (get_year_period_value, loginSummaryAgg, 'year'),
        (get_half_period_value, loginSummaryAgg, 'half'),
        (get_quarter_period_value, loginSummaryAgg, 'quarter')
    ]:
        for period_str, p_start, p_end in period_func(start_date.year):
            if start_date <= p_start and end_date >= p_end and not is_range_used(p_start, p_end, used_ranges):
                summary_rows = get_summary_rows_agg(
                    summary_func,
                    period_type=period_type,
                    period_value=period_str,
                    join_users=True,
                    group_fields=[Users.company]
                )
                if summary_rows:
                    used_ranges.append((p_start, p_end))
                    update_company_duration(summary_rows, company_field='company')
    
    used_ranges.sort(key=lambda x: x[0])
    current = start_date
        
    for used_start, used_end in used_ranges:
        if current < used_start:
            current_end = used_start - datetime.timedelta(days=1)
            if current <= current_end:
                if current < (datetime.date.today() - datetime.timedelta(days=1)):
                    try:
                        rows = get_summary_rows_day(
                            loginSummaryDay,
                            start_date=current,
                            end_date=min(current_end, datetime.date.today() - datetime.timedelta(days=2)),
                            join_users=True,
                            group_fields=[Users.company]
                        )
                        update_company_duration(rows, company_field='company')

                    except Exception as e:
                        logging.error(f"Error in summary_day_rows query: {e}")
                        return {
                            'has_data': False,
                            'company': None,
                            'duration': 0
                        }
                
                if current_end >= datetime.date.today() - datetime.timedelta(days=1):
                    local_tz = datetime.datetime.now().astimezone().tzinfo
                    utc_start_dt = datetime.datetime.combine(current, datetime.time.min, tzinfo=local_tz).astimezone(datetime.timezone.utc)
                    utc_end_dt = datetime.datetime.combine(used_start - datetime.timedelta(days=1), datetime.time.max, tzinfo=local_tz).astimezone(datetime.timezone.utc)
                    rows = get_summary_rows_history(
                        LoginHistory,
                        start_date=utc_start_dt,
                        end_date=utc_end_dt,
                        group_fields=[Users.company]
                    )
                    update_company_duration(rows, company_field='company')
                        
        current = max(current, used_end + datetime.timedelta(days=1))
        
    if current <= end_date:
        if current < (datetime.date.today() - datetime.timedelta(days=1)):
            rows = get_summary_rows_day(
                loginSummaryDay,
                start_date=current,
                end_date=min(end_date, datetime.date.today() - datetime.timedelta(days=2)),
                join_users=True,
                group_fields=[Users.company]
            )
            update_company_duration(rows, company_field='company')
        if end_date >= datetime.date.today() - datetime.timedelta(days=1):
            local_tz = datetime.datetime.now().astimezone().tzinfo
            utc_start_dt = datetime.datetime.combine(max(current, datetime.date.today() - datetime.timedelta(days=1)), datetime.time.min, tzinfo=local_tz).astimezone(datetime.timezone.utc)
            utc_end_dt = datetime.datetime.combine(end_date, datetime.time.max, tzinfo=local_tz).astimezone(datetime.timezone.utc)
            rows = get_summary_rows_history(
                LoginHistory,
                start_date=utc_start_dt,
                end_date=utc_end_dt,
                group_fields=[Users.company]
            )
            update_company_duration(rows, company_field='company')
    
    if company_duaration_map:
        sorted_companies = sorted(company_duaration_map.items(), key=lambda x: x[1], reverse=True)
        sorted_companies_by_low = sorted(company_duaration_map.items(), key=lambda x: x[1])
        return {
            'has_data': True,
            'top': [(company, duration) for company, duration in sorted_companies[:3]],
            'bottom': [(company, duration) for company, duration in sorted_companies_by_low[:3]],
        }
    else:
        return {
            'has_data': False,
            'company': None,
            'duration': 0
        }
    
               
def get_connection_summary_mixed(start_date, end_date, scope, filter_value=None):
    result = {
        'has_data': False,
        'total_duration': datetime.timedelta(0),
        'worktime_duration': datetime.timedelta(0),
        'offhour_duration': datetime.timedelta(0),
        'internal_count': 0,
        'external_count': 0
    }
    
    used_ranges = []
    for period_func, summary_func, period_scope in [
        (get_year_period_value, loginSummaryAgg, 'year'),
        (get_half_period_value, loginSummaryAgg, 'half'),
        (get_quarter_period_value, loginSummaryAgg, 'quarter')
    ]:
        for period_str, p_start, p_end in period_func(start_date.year):
            if start_date <= p_start and end_date >= p_end and not is_range_used(p_start, p_end, used_ranges):
                data = get_connection_summary_agg(period_scope, period_str, scope, filter_value)
                if data['has_data']:
                    result['has_data'] = True
                    result['total_duration'] += data['total_duration']
                    result['worktime_duration'] += data['worktime_duration']
                    result['offhour_duration'] += data['offhour_duration']
                    result['internal_count'] += data['internal_count']
                    result['external_count'] += data['external_count']
                    used_ranges.append((p_start, p_end))
                    
    used_ranges.sort(key=lambda x: x[0])
    current = start_date
    
    for used_start, used_end in used_ranges:
        if current < used_start:
            day_data = get_connection_summary_day(current, used_start - datetime.timedelta(days=1), scope, filter_value)
            if day_data['has_data']:
                result['has_data'] = True
                result['total_duration'] += day_data['total_duration']
                result['worktime_duration'] += day_data['worktime_duration']
                result['offhour_duration'] += day_data['offhour_duration']
                result['internal_count'] += day_data['internal_count']
                result['external_count'] += day_data['external_count']
        current = max(current, used_end + datetime.timedelta(days=1))
        
    if current <= end_date:
        day_data = get_connection_summary_day(current, end_date, scope, filter_value)
        if day_data['has_data']:
            result['has_data'] = True
            result['total_duration'] += day_data['total_duration']
            result['worktime_duration'] += day_data['worktime_duration']
            result['offhour_duration'] += day_data['offhour_duration']
            result['internal_count'] += day_data['internal_count']
            result['external_count'] += day_data['external_count']
            
    return result               
                    
def get_connection_summary_day(start_date, end_date, scope, filter_value=None):
    total = datetime.timedelta(0)
    work = datetime.timedelta(0)
    off = datetime.timedelta(0)
    internal = 0
    external = 0
    has_data = False
        
    if start_date < (datetime.date.today() - datetime.timedelta(days=1)):
        filters = [
            loginSummaryDay.period_value >= start_date,
            loginSummaryDay.period_value <= min(end_date, datetime.date.today() - datetime.timedelta(days=2))
        ]
        query = db.session.query(loginSummaryDay).join(Users, Users.id == loginSummaryDay.user_id_key)
        
        if scope == 'user' and filter_value:
            filters.append(loginSummaryDay.user_id_key == filter_value)
        elif scope == 'department' and filter_value:
            parts = filter_value.split('||', 1)
            if len(parts) == 2:
                company_name, department_name = parts
                filters.append(Users.company == company_name)
                filters.append(Users.department == department_name)
            else:
                department_name = parts[0]
                filters.append(Users.department == department_name)
        elif scope == 'company' and filter_value:
            filters.append(Users.company == filter_value)
        
        datas = query.filter(*filters).all()
        for data in datas:
            has_data = True
            total += data.total_duration or datetime.timedelta(0)
            work += data.worktime_duration or datetime.timedelta(0)
            off += data.offhour_duration or datetime.timedelta(0)
            internal += data.internal_count or 0
            external += data.external_count or 0
    
    if end_date >= (datetime.date.today() - datetime.timedelta(days=1)):
        local_tz = datetime.datetime.now().astimezone().tzinfo
        utc_start_dt = datetime.datetime.combine(max(start_date, datetime.date.today() - datetime.timedelta(days=1)), datetime.time.min, tzinfo=local_tz).astimezone(datetime.timezone.utc)
        utc_end_dt = datetime.datetime.combine(end_date, datetime.time.max, tzinfo=local_tz).astimezone(datetime.timezone.utc)       
        
        query = db.session.query(LoginHistory)
        
        if scope in ['department', 'company']:
            query = query.join(Users, LoginHistory.user_id == Users.id)
        
        filters = [
            LoginHistory.login_time >= utc_start_dt,
            LoginHistory.login_time <= utc_end_dt
        ]
        
        if scope == 'user' and filter_value:
            filters.append(LoginHistory.user_id == filter_value)
        elif scope == 'department' and filter_value:
            parts = filter_value.split('||', 1)
            if len(parts) == 2:
                company_name, department_name = parts
                filters.append(Users.company == company_name)
                filters.append(Users.department == department_name)
            else:
                department_name = parts[0]
                filters.append(Users.department == department_name)
        elif scope == 'company' and filter_value:
            filters.append(Users.company == filter_value)
        
        datas = query.filter(*filters).all()
        if datas:
            has_data = True            
            for record in datas:
                if record.login_time is None or record.logout_time is None:
                    continue
                
                duration = record.session_duration or datetime.timedelta(0)
                total += duration
                
                login_locale = record.login_time.astimezone()
                logout_locale = record.logout_time.astimezone()
                if login_locale.hour >= 8 and logout_locale.hour <= 18:
                    work += duration
                else:
                    off += duration

                if is_internal_ip(record.ip_address):
                    internal += 1
                else:
                    external += 1

    return {
        'has_data': has_data,
        'total_duration': total,
        'worktime_duration': work,
        'offhour_duration': off,
        'internal_count': internal,
        'external_count': external
    }

def is_internal_ip(ip_str):
    try:
        ip = ipaddress.ip_address(ip_str)
        return (ip.version == 4) and any(
            isinstance(start, ipaddress.IPv4Address) and isinstance(end, ipaddress.IPv4Address)
            and start <= ip <= end
            for start, end in ip_range_list
        )
    except Exception as e:
        logging.error(f"Error in is_internal_ip for IP {ip_str}: {e}")
        return False
    
def get_connection_summary_agg(period_type, period_value, scope, filter_value=None):
    base_filter = (
        loginSummaryAgg.period_type == period_type,
        loginSummaryAgg.period_value == period_value
    )

    if scope == 'user' and filter_value:
        # Users 조인 불필요
        q = (db.session.query(
                func.sum(loginSummaryAgg.total_duration).label('total'),
                func.sum(loginSummaryAgg.worktime_duration).label('work'),
                func.sum(loginSummaryAgg.offhour_duration).label('off'),
                func.sum(loginSummaryAgg.internal_count).label('internal'),
                func.sum(loginSummaryAgg.external_count).label('external'),
            )
            .filter(*base_filter, loginSummaryAgg.user_id_key == filter_value))
    else:
        # 현재 조직 기준 필터 필요 → Users 조인
        q = (db.session.query(
                func.sum(loginSummaryAgg.total_duration).label('total'),
                func.sum(loginSummaryAgg.worktime_duration).label('work'),
                func.sum(loginSummaryAgg.offhour_duration).label('off'),
                func.sum(loginSummaryAgg.internal_count).label('internal'),
                func.sum(loginSummaryAgg.external_count).label('external'),
            )
            .join(Users, Users.id == loginSummaryAgg.user_id)
            .filter(*base_filter))

        if scope == 'department' and filter_value:
            parts = filter_value.split('||', 1)
            if len(parts) == 2:
                company_name, department_name = parts
                q = q.filter(Users.company == company_name,
                             Users.department == department_name)
            else:
                q = q.filter(Users.department == parts[0])

        elif scope == 'company' and filter_value:
            q = q.filter(Users.company == filter_value)

    row = q.one()  # 매칭 없으면 NULL들인 1행이 반환됨(Postgres)

    total    = row.total    or datetime.timedelta(0)
    work     = row.work     or datetime.timedelta(0)
    off      = row.off      or datetime.timedelta(0)
    internal = int(row.internal or 0)
    external = int(row.external or 0)

    has_data = any([total, work, off, internal, external])

    return {
        'has_data': has_data,
        'total_duration': total,
        'worktime_duration': work,
        'offhour_duration': off,
        'internal_count': internal,
        'external_count': external
    }
        
def get_summary_rows_agg(model, period_type, period_value, group_fields, join_users=False, extra_filter=None):    
    query = db.session.query(*group_fields, func.sum(model.total_duration).label('total'))
    
    if join_users:
        query = query.join(Users, Users.id == model.user_id_key)
             
    query = query.filter(
            model.period_type == period_type,
            model.period_value == period_value
        )
    
    if extra_filter:
        query = query.filter(*extra_filter)
        
    query = query.group_by(*group_fields)
    
    # actual_query = query.statement.compile(compile_kwargs={"literal_binds": True})
    # logging.debug(f"[get_summary_rows_agg] {actual_query}")     
    return query.all()

def get_summary_rows_day(model, start_date, end_date, group_fields, join_users=False, extra_filter=None):
    query = db.session.query(*group_fields, func.sum(model.total_duration).label('total'))
    
    if join_users:
        query = query.join(Users, Users.id == model.user_id_key)

    query = query.filter(
            model.period_value >= start_date,
            model.period_value <= end_date
        )
    
    if extra_filter is not None:
        query = query.filter(*extra_filter)
        
    query = query.group_by(*group_fields)
    
    # logging.debug(query.statement.compile(compile_kwargs={"literal_binds": True}))
    return query.all()

def get_summary_rows_history(model, start_date, end_date, group_fields, join_users=True):
    query = db.session.query(*group_fields, func.sum(model.session_duration).label('total'))
    
    if join_users:
        query = query.join(Users, Users.id == model.user_id)
        
    query = query.filter(
            model.login_time >= start_date,
            model.login_time <= end_date
        ) \
        .group_by(*group_fields)
    
    # logging.debug(query.statement.compile(compile_kwargs={"literal_binds": True}))
    return query.all()



def get_unique_ip_counts(start_date, end_date, scope, filter_value=None):
    """
    LoginHistory 테이블에서 주어진 기간 동안의 고유 IP 주소 개수를 반환합니다.
    """
    base_query = db.session.query(LoginHistory.ip_address, LoginHistory.user_id).distinct()
    
    #공통 필터 설정: 날짜 범위
    local_tz = datetime.datetime.now().astimezone().tzinfo
    utc_start_dt = datetime.datetime.combine(start_date, datetime.time.min, tzinfo=local_tz).astimezone(datetime.timezone.utc)
    utc_end_dt = datetime.datetime.combine(end_date, datetime.time.max, tzinfo=local_tz).astimezone(datetime.timezone.utc)
    
    filters = [
        LoginHistory.login_time >= utc_start_dt,
        LoginHistory.login_time <= utc_end_dt,
        LoginHistory.ip_address != None,
        LoginHistory.ip_address != ''
    ]
    
    if scope in ['department', 'company']:
        base_query = base_query.join(Users, LoginHistory.user_id == Users.id)

    if scope == 'user' and filter_value:
        filters.append(LoginHistory.user_id == filter_value)
    elif scope == 'department' and filter_value:
        parts = filter_value.split('||', 1)
        if len(parts) == 2:
            company_name, department_name = parts
            filters.extend([Users.company == company_name, Users.department == department_name])
        else:
            department_name = parts[0]
            filters.append(Users.department == department_name)
    elif scope == 'company' and filter_value:
        filters.append(Users.company == filter_value)
    
    ip_inet = cast(LoginHistory.ip_address, INET)
    ip_family = func.family(ip_inet)
    
    # 내부 IP 확인을 위한 SQL 조건 생성 (ip_range_list 캐시 사용/ IPv4 형식만 체크)
    internal_ip_conditions = [
        case(
            (ip_family == 4,
             ip_inet.between(cast(str(start_ip), INET), cast(str(end_ip), INET))),
            else_=false()
        )
        for start_ip, end_ip in ip_range_list
    ]
            
    internal_ip_filter = or_(*internal_ip_conditions) if internal_ip_conditions else false()
    
    internal_user_ip_pairs = base_query.filter(*filters, internal_ip_filter).all()
    #logging.debug(f"Found unique internal (IP, User) pairs: {internal_user_ip_pairs}")
    
    external_user_ip_pairs = base_query.filter(*filters, ~internal_ip_filter).all()
    #logging.debug(f"Found unique external (IP, User) pairs: {external_user_ip_pairs}")

    return {'internal_count': len(internal_user_ip_pairs), 'external_count': len(external_user_ip_pairs)}