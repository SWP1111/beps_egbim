from extensions import db
from models import Users

def get_user_ids_by_scope(scope, filter_value):
    """
    scope에 따라 사용자 ID 목록 가져오기
    """
    query = db.session.query(Users.id)
    
    if scope == 'company':
        query = query.filter(Users.company == filter_value)
    elif scope == 'department':
        parts = filter_value.split('||', 1)
        if len(parts) == 2:
            query = query.filter(Users.company == parts[0], Users.department == parts[1])
        else:
            query = query.filter(Users.department == parts[0])
    elif scope == 'user':
        query = query.filter(Users.id == filter_value)
    
    return [row.id for row in query.all()]