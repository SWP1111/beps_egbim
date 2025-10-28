from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import OperationalError # 예외 처리
from sqlalchemy.sql import text
from sqlalchemy import ForeignKey

app = Flask(__name__)

# PostgreSQL 데이터베이스 연결 설정
# 포맷: postgresql://username:password@hostname/database
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:postgres@172.16.10.191:15432/beps'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# SQLAlchemy 초기화
db = SQLAlchemy(app)


class Roles(db.Model):
    __tablename__ = 'roles'
    role_id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.Text)
    time_stamp = db.Column(db.BigInteger)

    def to_dict(self):
        return {
            'role_id': self.role_id,
            'role_name': self.role_name,
            'time_stamp': self.time_stamp
        }
 
class ContentAccessGroups(db.Model):
    __tablename__ = 'content_access_groups'
    access_group_id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.Text)
    time_stamp = db.Column(db.BigInteger)

    def to_dict(self):
        return {
            'access_group_id': self.access_group_id,
            'group_name': self.group_name,
            'time_stamp': self.time_stamp
        }
            
class Users(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Text, primary_key=True)
    password = db.Column(db.Text)
    company = db.Column(db.Text)
    department = db.Column(db.Text)
    position = db.Column(db.Text)
    name = db.Column(db.Text)
    access_group_id = db.Column(db.Integer, ForeignKey('content_access_groups.access_group_id'))
    role_id = db.Column(db.Integer, ForeignKey('roles.role_id'))
    time_stamp = db.Column(db.BigInteger)

    def to_dict(self):
        return {
            'id': self.id,
            'password': self.password,
            'company': self.company,
            'department': self.department,
            'position': self.position,
            'name': self.name,
            'access_group_id': self.access_group_id,
            'role_id': self.role_id,
            'time_stamp': self.time_stamp
        }


# DB 연결 상태 확인 API
@app.route('/db_status', methods=['GET'])
def check_db_status():
    try:
        print("db.sesseion.execute", flush=True)
        db.session.execute(text('SELECT 1'))
        return jsonify({'status': 'OK'})
    except OperationalError as e:
        return jsonify({'error': str(e)}), 500

# 유효한 값인지 확인하는 함수, key가 data에 존재하고 '@' 또는 -1이 아닌 값이면 유효한 값으로 판단
def is_valid(key, data):
    return key in data and data[key] not in ('@', -1)

# Users 테이블 Row 조회 API
@app.route('/user', methods=['GET'])
def get_user():
    try:
        user_id = request.args.get('id')
        if user_id is None:
            return jsonify({'error': 'Please provide id'}), 400 # 400: Bad Request
        user = Users.query.filter_by(id=user_id).first()
        if user:
            return jsonify(user.to_dict())
        else:
            return jsonify({'error': 'User not found'}), 404    # 404: Not Found
    except OperationalError as e:
        return jsonify({'error': str(e)}), 500  # 500: Internal Server Error

@app.route('/user_auth_time', methods=['GET'])
def get_user_auth_time():
    try:
        user_id = request.args.get('id')
        
        if user_id is None:
            return jsonify({'error': 'Please provide id'}), 400 # 400: Bad Request
        
        user = Users.query.filter_by(id=user_id).first()
        if user:
            return jsonify(user.time_stamp)
        else:
            return jsonify({'error': 'User not found'}), 404    # 404: Not Found
    except OperationalError as e:
        return jsonify({'error': str(e)}), 500
       
# Users 테이블 Row Insert/Update API
@app.route('/user', methods=['POST'])
def upsert_user():
    try:
        data = request.get_json() # JSON 데이터를 가져옴
        if not data or 'id' not in data:
            return jsonify({'error': 'Please provide id'}), 400
        
        user_id = data.get('id')
        user = Users.query.filter_by(id=user_id).first()
        if user is None:    # 새로운 Row 추가
            user = Users(id=user_id)
            user.password = data.get('password')
            if(is_valid('company', data)): user.company = data.get('company')
            if(is_valid('department', data)): user.department = data.get('department')
            if(is_valid('position', data)): user.position = data.get('position')
            if(is_valid('name', data)): user.name = data.get('name')
            if(is_valid('access_group_id', data)): user.access_group_id = data.get('access_group_id')
            if(is_valid('role_id', data)): user.role_id = data.get('role_id')
            db.session.add(user)
            db.session.commit()
        else:   # Row 업데이트
            if(is_valid('password',data)): user.password = data.get('password')
            if(is_valid('company',data)):user.company = data.get('company')
            if(is_valid('department',data)):user.department = data.get('department')
            if(is_valid('position',data)):user.position = data.get('position')
            if(is_valid('name',data)):user.name = data.get('name')
            if(is_valid('access_group_id',data)):user.access_group_id = data.get('access_group_id')
            if(is_valid('role_id',data)):user.role_id = data.get('role_id')
            db.session.commit()
        return jsonify(user.to_dict()), 201
    except OperationalError as e:   # DB 접속 오류 처리
        return jsonify({'error': str(e)}), 500
        
# Roles 테이블 조회 API
@app.route('/roles', methods=['GET'])
def get_roles():
    try:
        roles = Roles.query.all()
        return jsonify([role.to_dict() for role in roles])
    except OperationalError as e:
        return jsonify({'error': str(e)}), 500

# Roles 테이블 Row 추가 API
@app.route('/roles', methods=['POST'])
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

if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False)