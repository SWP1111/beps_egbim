from sqlalchemy import CheckConstraint
from extensions import db
from sqlalchemy.sql import func, text
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timezone
class Roles(db.Model):
    __tablename__ = 'roles'
    role_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    role_name = db.Column(db.Text)
    time_stamp = db.Column(db.BigInteger)
    description = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'role_id': self.role_id,
            'role_name': self.role_name,
            'time_stamp': self.time_stamp,
            'description': self.description
        }

class ContentAccessGroups(db.Model):
    __tablename__ = 'content_access_groups'
    access_group_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
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
    access_group_id = db.Column(db.Integer, db.ForeignKey('content_access_groups.access_group_id'))
    role_id = db.Column(db.Integer, db.ForeignKey('roles.role_id'))
    time_stamp = db.Column(db.BigInteger)
    logout_time = db.Column(db.DateTime(timezone=True))
    login_time = db.Column(db.DateTime(timezone=True))
    is_deleted = db.Column(db.Boolean, default=False)
    phone = db.Column(db.Text, nullable=True) 
    email = db.Column(db.Text, nullable=True)

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
            'time_stamp': self.time_stamp,
            'logout_time': self.logout_time,
            'login_time': self.login_time,
            'is_deleted': self.is_deleted,
            'phone': self.phone,
            'email': self.email
        }

class LoginHistory(db.Model):
    __tablename__ = 'login_history'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Text, db.ForeignKey('users.id'))
    ip_address = db.Column(db.Text)
    login_time = db.Column(db.DateTime(timezone=True))
    logout_time = db.Column(db.DateTime(timezone=True))
    session_duration = db.Column(db.Interval)
    time_stamp = db.Column(db.BigInteger)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'ip_address': self.ip_address,
            'login_time': self.login_time,
            'logout_time': self.logout_time,
            'session_duration': self.session_duration,
            'time_stamp': self.time_stamp
        }

class loginSummaryDay(db.Model):
    __tablename__ = 'login_summary_day'
    period_value = db.Column(db.Date)
    company_id = db.Column(db.Integer)
    company = db.Column(db.Text)
    department = db.Column(db.Text)
    user_id = db.Column(db.Text)
    user_name = db.Column(db.Text)
    total_duration = db.Column(db.Interval)
    worktime_duration = db.Column(db.Interval)
    offhour_duration = db.Column(db.Interval)
    internal_count = db.Column(db.Integer)
    external_count = db.Column(db.Integer)
    company_key = db.Column(db.Text)
    department_key = db.Column(db.Text)
    user_id_key = db.Column(db.Text)
    
    __table_args__ = (
        db.PrimaryKeyConstraint('period_value', 'company_key', 'department_key', 'user_id_key',
                                name='login_summary_day_pkey'
                                ),
    )
    
    def to_dict(self):
        return {
            'period_value': self.period_value,
            'company_id': self.company_id,
            'company': self.company,
            'department': self.department,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'total_duration': str(self.total_duration),
            'worktime_duration': str(self.worktime_duration),
            'offhour_duration': str(self.offhour_duration),
            'internal_count': self.internal_count,
            'external_count': self.external_count,
            'company_key': self.company_key,
            'department_key': self.department_key,
            'user_id_key': self.user_id_key
        }
        
class loginSummaryAgg(db.Model):
    __tablename__ = 'login_summary_agg'
    period_type = db.Column(db.Text)
    period_value = db.Column(db.Text)
    company_id = db.Column(db.Integer)
    company = db.Column(db.Text)
    department = db.Column(db.Text)
    user_id = db.Column(db.Text)
    user_name = db.Column(db.Text)
    total_duration = db.Column(db.Interval)
    worktime_duration = db.Column(db.Interval)
    offhour_duration = db.Column(db.Interval)
    internal_count = db.Column(db.Integer)
    external_count = db.Column(db.Integer)
    company_key = db.Column(db.Text)
    department_key = db.Column(db.Text)
    user_id_key = db.Column(db.Text)
    
    __table_args__ = (
        db.PrimaryKeyConstraint('period_type', 'period_value', 'company_key', 'department_key', 'user_id_key',
                                name='login_summary_agg_pkey'
                                ),
    )
    
    def to_dict(self):
        return {
            'period_type': self.period_type,
            'period_value': self.period_value,
            'company_id': self.company_id,
            'company': self.company,
            'department': self.department,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'total_duration': self.total_duration,
            'worktime_duration': self.worktime_duration,
            'offhour_duration': self.offhour_duration,
            'internal_count': self.internal_count,
            'external_count': self.external_count,
            'company_key': self.company_key,
            'department_key': self.department_key,
            'user_id_key': self.user_id_key
        }
    
         
class ContentViewingHistory(db.Model):
    __tablename__ = 'content_viewing_history'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Text, db.ForeignKey('users.id'))
    file_id = db.Column(db.Text, db.ForeignKey('content_rel_pages.id'))
    file_type = db.Column(db.String(10), nullable=False, server_default='page')
    start_time = db.Column(db.DateTime(timezone=True))
    end_time = db.Column(db.DateTime(timezone=True))
    stay_duration = db.Column(db.Interval)
    ip_address = db.Column(db.Text)
    time_stamp = db.Column(db.BigInteger)

    __table_args__ = (
        CheckConstraint("file_type IN ('page', 'detail')", name='chk_file_type'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'file_id': self.file_id,
            'file_type': self.file_type,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'stay_duration': self.stay_duration,
            'ip_address': self.ip_address,
            'time_stamp': self.time_stamp
        }

class LearningSummaryDay(db.Model):
    __tablename__ = 'learning_summary_day'
    stat_date = db.Column(db.Date)
    company_id = db.Column(db.Integer)
    company = db.Column(db.Text)
    department_id = db.Column(db.Integer)
    department = db.Column(db.Text)
    user_id = db.Column(db.Text)
    user_name = db.Column(db.Text)
    channel_id = db.Column(db.Integer)
    channel_name = db.Column(db.Text)
    total_duration = db.Column(db.Interval)
    company_key = db.Column(db.Text)
    department_key = db.Column(db.Text)
    user_id_key = db.Column(db.Text)
    channel_key = db.Column(db.Text)

    __table_args__ = (
        db.PrimaryKeyConstraint('stat_date', 'company_key', 'department_key', 'user_id_key', 'channel_key',
                                name='pk_learning_summary_day'
                                ),
    )
    
    def to_dict(self):
        return {
            'stat_date': self.stat_date,
            'company_id': self.company_id,
            'company': self.company,
            'department': self.department,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'channel_id': self.channel_id,
            'channel_name': self.channel_name,
            'total_duration': str(self.total_duration),
            'company_key': self.company_key,
            'department_key': self.department_key,
            'user_id_key': self.user_id_key,
            'folder_key': self.folder_key
        }

class LearningSummaryAgg(db.Model):
    __tablename__ = 'learning_summary_agg'
    period_type = db.Column(db.Text)
    period_value = db.Column(db.Text)
    company_id = db.Column(db.Integer)
    company = db.Column(db.Text)
    deparment_id = db.Column(db.Integer)
    department = db.Column(db.Text)
    user_id = db.Column(db.Text)
    user_name = db.Column(db.Text)
    channel_id = db.Column(db.Integer)
    channel_name = db.Column(db.Text)
    total_duration = db.Column(db.Interval)
    company_key = db.Column(db.Text)
    department_key = db.Column(db.Text)
    user_id_key = db.Column(db.Text)
    channel_key = db.Column(db.Text)
    
    __table_args__ = (
        db.PrimaryKeyConstraint('period_value', 'company_key', 'department_key', 'user_id_key', 'channel_key',
                                name='pk_learning_summary_agg'
                                ),
    )
    
    def to_dict(self):
        return {
            'period_type': self.period_type,
            'period_value': self.period_value,
            'company_id': self.company_id,
            'company': self.company,
            'department': self.department,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'channel_id': self.channel_id,
            'channel_name': self.channel_name,
            'total_duration': str(self.total_duration),
            'company_key': self.company_key,
            'department_key': self.department_key,
            'user_id_key': self.user_id_key,
            'folder_key': self.folder_key
        }
        
class ContentPointRecord(db.Model):
    __tablename__ = 'content_point_record'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Text, db.ForeignKey('users.id'), nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey('content_rel_pages.id'), nullable=False)
    point = db.Column(db.Integer, nullable=False)
    earned_times = db.Column(JSONB, nullable=False, default=list)
    file_type = db.Column(db.String(10), nullable=False, server_default='page')
    
    __table_args__ = (
        CheckConstraint("file_type IN ('page', 'detail')", name='chk_file_type'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'file_id': self.file_id,
            'point': self.point,
            'earned_times': self.earned_times
        }

class LearningCompletionHistory(db.Model):
    __tablename__ = 'learning_completion_history'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Text, nullable=False)
    page_id = db.Column(db.Integer, nullable=False)
    completed_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    total_duration = db.Column(db.Interval, nullable=False)
    
    __table_args__ = (
    db.UniqueConstraint('user_id', 'page_id', name='uq_user_page'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'page_id': self.page_id,
            'completed_at': self.completed_at,
            'total_duration': str(self.total_duration)
        }
    
class ContentRelChannels(db.Model):
    __tablename__ = 'content_rel_channels'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=False), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=False), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_deleted = db.Column(db.Boolean, default=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'is_deleted': self.is_deleted
        }

class ContentRelFolders(db.Model):
    __tablename__ = 'content_rel_folders'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('content_rel_folders.id'))
    channel_id = db.Column(db.Integer, db.ForeignKey('content_rel_channels.id'))
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=False), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=False), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_deleted = db.Column(db.Boolean, default=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'parent_id': self.parent_id,
            'channel_id': self.channel_id,
            'name': self.name,
            'description': self.description,
            'crated_at': self.created_at,
            'updated_at': self.updated_at,
            'is_deleted': self.is_deleted
        }

class ContentRelPages(db.Model):
    __tablename__ = 'content_rel_pages'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    folder_id = db.Column(db.Integer, db.ForeignKey('content_rel_folders.id'))
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.Text)
    object_id = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime(timezone=False), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=False), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_deleted = db.Column(db.Boolean, default=False)
    
    def check_r2_content_exists(self, use_cache=True):
        """
        Check if this page's content actually exists in R2 storage
        Uses the R2StorageService for proper separation of concerns
        """
        from services.r2_storage_service import R2StorageService
        
        return R2StorageService.check_page_content_exists(
            page_id=self.id,
            page_name=self.name,
            page_object_id=self.object_id,
            updated_at=self.updated_at,
            use_cache=use_cache
        )
    
    @property
    def has_content(self):
        """Computed property that checks if actual file exists in R2 storage"""
        return self.check_r2_content_exists()
    
    def to_dict(self):
        return {
            'id': self.id,
            'folder_id': self.folder_id,
            'name': self.name,
            'description': self.description,
            'object_id': self.object_id,
            'has_content': self.has_content,  # Uses the property
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'is_deleted': self.is_deleted
        }

class ContentRelPageDetails(db.Model):
    __tablename__ = 'content_rel_page_details'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    page_id = db.Column(db.Integer, db.ForeignKey('content_rel_pages.id'))
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.Text)
    object_id = db.Column(db.String, nullable=True)
    # has_content = db.Column(db.Boolean, default=False)  # Temporarily commented until DB migration
    created_at = db.Column(db.DateTime(timezone=False), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=False), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_deleted = db.Column(db.Boolean, default=False)
    
    def check_r2_content_exists(self, use_cache=True):
        """
        Check if this page detail's content actually exists in R2 storage
        Uses the R2StorageService for proper separation of concerns
        """
        from services.r2_storage_service import R2StorageService
        
        return R2StorageService.check_page_detail_content_exists(
            detail_id=self.id,
            detail_name=self.name,
            detail_object_id=self.object_id,
            updated_at=self.updated_at,
            use_cache=use_cache
        )
    
    @property
    def has_content(self):
        """Computed property that checks if actual file exists in R2 storage"""
        # For performance, we can add caching here in the future
        # For now, use the method that actually checks R2
        return self.check_r2_content_exists()
    
    def to_dict(self):
        return {
            'id': self.id,
            'page_id': self.page_id,
            'name': self.name,
            'description': self.description,
            'object_id': self.object_id,
            'has_content': self.has_content,  # Uses the property
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'is_deleted': self.is_deleted
        }

class Assignees(db.Model):
    __tablename__ = 'assignees'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Text, db.ForeignKey('users.id'), nullable=True, unique=True)
    name = db.Column(db.Text, nullable=False)
    position = db.Column(db.Text, nullable=True)
    
    def to_dict(self):
        return {
            'id' : self.id,
            'user_id' : self.user_id,
            'name' : self.name,
            'position' : self.position
        }
        
class ContentManager(db.Model):
    __tablename__ = 'content_manager'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    file_id = db.Column(db.Integer, db.ForeignKey('content_rel_pages.id'), nullable=True)
    folder_id = db.Column(db.Integer, db.ForeignKey('content_rel_folders.id'), nullable=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('content_rel_channels.id'), nullable=True)
    type = db.Column(db.String(10), nullable=False)  # 'file', 'folder', or 'channel'
    assignee_id = db.Column(db.Integer, db.ForeignKey('assignees.id'), nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'file_id': self.file_id,
            'folder_id': self.folder_id,
            'channel_id': self.channel_id,
            'type': self.type,
            'assignee_id': self.assignee_id
        }

class PushMessages(db.Model):
    __tablename__ = 'push_messages'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Text, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.Text)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'message': self.message,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat()
        }
        
class IpRange(db.Model):
    __tablename__ = 'ip_ranges'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    start_ip = db.Column(db.Text, nullable=False)
    end_ip = db.Column(db.Text, nullable=False)
    label = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'start_ip': self.start_ip,
            'end_ip': self.end_ip,
            'label': self.label
        }          

class MemoData(db.Model):
    __tablename__ = 'memos'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    modified_at = db.Column(db.DateTime(timezone=True), server_default=func.now())  # Registration date - only updates when content changes
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    title = db.Column(db.String, nullable=True)
    content = db.Column(db.String, nullable=True)
    path = db.Column(db.String, nullable=True)
    file_id = db.Column(db.Integer, db.ForeignKey('content_rel_pages.id'), nullable=True)
    folder_id = db.Column(db.Integer, db.ForeignKey('content_rel_folders.id'), nullable=True)
    rel_position_x = db.Column(db.Float, nullable=False)  # double in C#
    rel_position_y = db.Column(db.Float, nullable=False)  # double in C#
    world_position_x = db.Column(db.Float, nullable=False)  # double in C#
    world_position_y = db.Column(db.Float, nullable=False)  # double in C#
    world_position_z = db.Column(db.Float, nullable=False)  # double in C#
    status = db.Column(db.Integer, nullable=False)  # uint in C#
    type = db.Column(db.Integer, nullable=False, default=0)  # 0: 독후감, 1: 제안, 2: 질문

    user = db.relationship('Users', backref=db.backref('memos', lazy=True))
    file = db.relationship('ContentRelPages', backref=db.backref('memos', lazy=True))
    folder = db.relationship('ContentRelFolders', backref=db.backref('memos', lazy=True))

    def to_dict(self):
        # Convert type int to string
        type_mapping = {
            0: "질문",
            1: "의견", 
        }
        
        # Convert status int to string
        status_mapping = {
            0: "답변대기",
            1: "답변완료",
            2: "처리완료"
        }
        
        return {
            'id': self.id,
            'created_at': self.created_at,  # Memo creation date - never changes
            'modified_at': self.modified_at,  # Registration date (등록일) - only changes when content is modified
            'user_id': self.user_id,
            'title': self.title,
            'content': self.content,
            'path': self.path,
            'file_id': self.file_id,
            'folder_id': self.folder_id,
            'relPositionX': self.rel_position_x,  # Match C# JsonPropertyName
            'relPositionY': self.rel_position_y,  # Match C# JsonPropertyName
            'worldPositionX': self.world_position_x,  # Match C# JsonPropertyName
            'worldPositionY': self.world_position_y,  # Match C# JsonPropertyName
            'worldPositionZ': self.world_position_z,  # Match C# JsonPropertyName
            'status': self.status,  # Match C# JsonPropertyName
            'status_text': status_mapping.get(self.status, "알 수 없음"),
            'type': self.type,
            'type_text': type_mapping.get(self.type, "알 수 없음")
        }

class MemoReply(db.Model):
    __tablename__ = 'memo_replies'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    memo_id = db.Column(db.Integer, db.ForeignKey('memos.id'), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    modified_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_deleted = db.Column(db.Boolean, default=False)
    
    # Relationships
    memo = db.relationship('MemoData', backref=db.backref('replies', lazy=True))
    user = db.relationship('Users', backref=db.backref('memo_replies', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'memo_id': self.memo_id,
            'user_id': self.user_id,
            'content': self.content,
            'created_at': self.created_at,
            'modified_at': self.modified_at,
            'is_deleted': self.is_deleted,
            'user': self.user.to_dict() if self.user else None,
            'attachments': [attachment.to_dict() for attachment in self.attachments] if hasattr(self, 'attachments') else []
        }


class MemoReplyAttachment(db.Model):
    __tablename__ = 'memo_reply_attachments'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    memo_reply_id = db.Column(db.Integer, db.ForeignKey('memo_replies.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    object_key = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.BigInteger, default=0)
    content_type = db.Column(db.String(100))
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationship
    reply = db.relationship('MemoReply', backref=db.backref('attachments', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'memo_reply_id': self.memo_reply_id,
            'filename': self.filename,
            'object_key': self.object_key,
            'file_size': self.file_size,
            'content_type': self.content_type,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


# ========== Content Manager Refactoring Models ==========

class PageAdditionals(db.Model):
    """
    Track additional content files associated with pages
    Following naming convention: {page_prefix}_{content_number}.{ext}
    """
    __tablename__ = 'page_additionals'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    page_id = db.Column(db.Integer, db.ForeignKey('content_rel_pages.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    object_key = db.Column(db.String(500), nullable=False)  # R2 path
    file_extension = db.Column(db.String(10), nullable=False)
    content_number = db.Column(db.Integer, nullable=False)  # The XX in "001_XX.ext"
    file_size = db.Column(db.BigInteger, default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_deleted = db.Column(db.Boolean, default=False)

    # Relationships
    page = db.relationship('ContentRelPages', backref=db.backref('additionals', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('page_id', 'content_number', name='uq_page_content_number'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'page_id': self.page_id,
            'filename': self.filename,
            'object_key': self.object_key,
            'file_extension': self.file_extension,
            'content_number': self.content_number,
            'file_size': self.file_size,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_deleted': self.is_deleted
        }


class PendingContent(db.Model):
    """
    Track pending content uploads awaiting approval
    Supports both pages and additional content
    """
    __tablename__ = 'pending_content'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    content_type = db.Column(db.String(20), nullable=False)  # 'page' or 'additional'
    page_id = db.Column(db.Integer, db.ForeignKey('content_rel_pages.id'), nullable=False)
    additional_id = db.Column(db.Integer, db.ForeignKey('content_rel_page_details.id'), nullable=True)  # References page_details
    object_key = db.Column(db.String(500), nullable=False)  # R2 path in pending location
    filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.BigInteger, default=0)
    uploaded_by = db.Column(db.Text, db.ForeignKey('users.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    # Relationships
    page = db.relationship('ContentRelPages', backref=db.backref('pending_contents', lazy=True))
    detail = db.relationship('ContentRelPageDetails', foreign_keys=[additional_id], backref=db.backref('pending_contents', lazy=True))
    uploader = db.relationship('Users', backref=db.backref('uploaded_pending_contents', lazy=True))

    __table_args__ = (
        CheckConstraint("content_type IN ('page', 'additional')", name='chk_pending_content_type'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'content_type': self.content_type,
            'page_id': self.page_id,
            'additional_id': self.additional_id,
            'object_key': self.object_key,
            'filename': self.filename,
            'file_size': self.file_size,
            'uploaded_by': self.uploaded_by,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }


class ArchivedContent(db.Model):
    """
    Track archived versions of content (old versions before updates)
    """
    __tablename__ = 'archived_content'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    content_type = db.Column(db.String(20), nullable=False)  # 'page' or 'additional'
    original_page_id = db.Column(db.Integer, db.ForeignKey('content_rel_pages.id'), nullable=False)
    original_additional_id = db.Column(db.Integer, db.ForeignKey('content_rel_page_details.id'), nullable=True)  # References page_details
    object_key = db.Column(db.String(500), nullable=False)  # R2 path in archive/old
    archived_filename = db.Column(db.String(255), nullable=False)  # With timestamp suffix
    file_size = db.Column(db.BigInteger, default=0)
    archived_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    archived_by = db.Column(db.Text, db.ForeignKey('users.id'), nullable=False)  # 책임자 who approved

    # Relationships
    original_page = db.relationship('ContentRelPages', backref=db.backref('archived_contents', lazy=True))
    original_detail = db.relationship('ContentRelPageDetails', foreign_keys=[original_additional_id], backref=db.backref('archived_contents', lazy=True))
    archiver = db.relationship('Users', backref=db.backref('archived_by_user', lazy=True))

    __table_args__ = (
        CheckConstraint("content_type IN ('page', 'additional')", name='chk_archived_content_type'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'content_type': self.content_type,
            'original_page_id': self.original_page_id,
            'original_additional_id': self.original_additional_id,
            'object_key': self.object_key,
            'archived_filename': self.archived_filename,
            'file_size': self.file_size,
            'archived_at': self.archived_at.isoformat() if self.archived_at else None,
            'archived_by': self.archived_by
        }

