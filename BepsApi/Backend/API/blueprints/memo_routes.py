from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import MemoData, Users, ContentManager, Assignees, ContentRelPages, MemoReply
import logging
import log_config
from log_config import get_memo_logger
from sqlalchemy import func, text, desc
import traceback
from datetime import datetime, timezone, time

api_memo_bp = Blueprint('memo', __name__)

# ?�� 메모 ?�용 로거 초기??
logger = get_memo_logger()

@api_memo_bp.route('/', methods=['POST'])
def create_memo():
    try:
        data = request.json
        if not data:
            logger.error("No JSON data provided in request")
            return jsonify({"error": "No JSON data provided"}), 400
            
        logger.info(f"Received POST request to /memo with data: {data}")
        
        # Validate foreign key constraints before creating memo to prevent ID increment on failure
        file_id = data.get('file_id')
        if file_id is not None:
            # Check if file_id exists in content_rel_pages
            file_exists = db.session.query(ContentRelPages.id).filter_by(id=file_id).first()
            if not file_exists:
                logger.error(f"file_id {file_id} does not exist in content_rel_pages")
                return jsonify({"error": f"file_id {file_id} does not exist"}), 400
        
        folder_id = data.get('folder_id')
        if folder_id is not None:
            # Check if folder_id exists in content_rel_folders (assuming this table exists)
            # This prevents foreign key violations before attempting insert
            folder_query = db.session.execute(text("SELECT 1 FROM content_rel_folders WHERE id = :folder_id"), {"folder_id": folder_id})
            if not folder_query.fetchone():
                logger.error(f"folder_id {folder_id} does not exist in content_rel_folders")
                return jsonify({"error": f"folder_id {folder_id} does not exist"}), 400
        
        current_time = datetime.now(timezone.utc)
        # Create memo with explicit values from request data
        memo = MemoData(
            modified_at=current_time,  # Set registration date (등록일) - will only update when content changes
            created_at=current_time,  # Set created_at to current time
            user_id=data.get('user_id'),
            type=int(data.get('type', 0)),  # Convert to int with default 0
            title=data.get('title'),
            content=data.get('content', ''),
            path=data.get('path'),
            file_id=data.get('file_id'),
            folder_id=data.get('folder_id'),
            rel_position_x=float(data['relPositionX']),  # Convert to float
            rel_position_y=float(data['relPositionY']),
            world_position_x=float(data['worldPositionX']),
            world_position_y=float(data['worldPositionY']),
            world_position_z=float(data['worldPositionZ']),
            status=int(data['status'])  # Convert to int
        )
        
        db.session.add(memo)
        db.session.commit()
        logger.info(f"Successfully created memo with id: {memo.id}")
        return jsonify({
            "modified_at": current_time,
            "id": memo.id
        }), 201
    except Exception as e:
        logger.error(f"Error creating memo: {str(e)}")
        db.session.rollback()  # Rollback on error
        return jsonify({"error": str(e)}), 500

@api_memo_bp.route('/', methods=['GET'])
@jwt_required(locations=['headers','cookies'])
def get_all_memos():
    try:
        logger.info("Received GET request to /memo")
        user_id = request.args.get('user_id')
        path = request.args.get('path')
        file_id = request.args.get('file_id')
        folder_id = request.args.get('folder_id')
        
        logger.info(f"Request parameters: user_id={user_id}, path={path}, file_id={file_id}, folder_id={folder_id}")
        
        # Get JWT identity (user_id from token)
        jwt_user_id = get_jwt_identity()
        logger.info(f"Authenticated user_id: {jwt_user_id}")
        
        # Fetch user information to check role
        user = Users.query.filter_by(id=jwt_user_id).first()
        
        if not user:
            logger.error(f"User not found for ID: {jwt_user_id}")
            return jsonify({"error": "User not found"}), 404
        
        logger.info(f"User role_id: {user.role_id}")
        
        # Base query
        query = MemoData.query
        
        # Apply filters based on parameters
        if path:
            query = query.filter(MemoData.path == path)
        if file_id:
            query = query.filter(MemoData.file_id == file_id)
        if folder_id:
            query = query.filter(MemoData.folder_id == folder_id)
            
        # Role-based access control       
        if user.role_id in [1, 2]:
            # Full managers (role_id 1,2) can see all memos
            logger.info(f"Full manager user {jwt_user_id} (role_id: {user.role_id}) can see all memos")
            # No additional filtering - managers see everything
        else:
            file_perm = db.session.query(ContentManager.id).join(
                Assignees, ContentManager.assignee_id == Assignees.id
            ).filter(
                Assignees.user_id == jwt_user_id,
                ContentManager.file_id.isnot(None),
                ContentManager.file_id == MemoData.file_id
            ).exists()
            
            folder_perm = db.session.query(ContentManager.id).join(
                Assignees, ContentManager.assignee_id == Assignees.id
            ).join(
                ContentRelPages, ContentRelPages.id == MemoData.file_id
            ).filter(
                Assignees.user_id == jwt_user_id,
                ContentManager.folder_id.isnot(None),
                ContentManager.folder_id == ContentRelPages.folder_id
            ).exists()

            query = query.filter((MemoData.user_id == jwt_user_id) | file_perm | folder_perm)
            logger.info(f"Regular user {jwt_user_id} (role_id: {user.role_id}) can see own memos and assigned content memos")
            
        # Initialize memos as empty list
        memos = []
        
        # Handle user_id case-insensitive search
        if user_id:
            # First try with the exact user_id
            first_query = query.filter(MemoData.user_id == user_id)
            memos = first_query.all()
            
            # If no results and user_id contains letters, try alternative case
            if not memos and any(c.isalpha() for c in user_id):
                import re
                # Extract letters and numbers
                match = re.match(r'([a-zA-Z]+)(\d+)', user_id)
                if match:
                    letters, numbers = match.groups()
                    # Try opposite case (upper if lower, lower if upper)
                    if letters.islower():
                        alt_user_id = letters.upper() + numbers
                    else:
                        alt_user_id = letters.lower() + numbers
                    
                    logger.info(f"No results for user_id: {user_id}, trying alternative: {alt_user_id}")
                    memos = query.filter(MemoData.user_id == alt_user_id).all()
        else:
            # If no user_id provided, use the query we've built
            memos = query.all()
            
        memos_list = [memo.to_dict() for memo in memos]
        logger.info(f"Returning {len(memos_list)} memos")
        return jsonify(memos_list), 200
    except Exception as e:
        logger.error(f"Error retrieving memos: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_memo_bp.route('/<int:id>', methods=['GET'])
def get_memo(id):
    memo = MemoData.query.get_or_404(id)
    return jsonify(memo.to_dict())

@api_memo_bp.route('/<int:id>', methods=['PUT'])
def update_memo(id):
    try:
        memo = MemoData.query.get_or_404(id)
        data = request.json
        if not data:
            logger.error("No JSON data provided in request")
            return jsonify({"error": "No JSON data provided"}), 400
            
        logger.info(f"Received PUT request to /memo/{id} with data: {data}")
        
        # Track if content fields change (not just status)
        content_changed = False
        
        # Check content fields and update them
        if 'content' in data and data['content'] != memo.content:
            memo.content = data['content']
            content_changed = True
            
        if 'title' in data and data['title'] != memo.title:
            memo.title = data['title']
            content_changed = True
            
        if 'user_id' in data and data['user_id'] != memo.user_id:
            memo.user_id = data['user_id']
            content_changed = True
            
        if 'path' in data and data['path'] != memo.path:
            memo.path = data['path']
            content_changed = True
            
        if 'file_id' in data and data['file_id'] != memo.file_id:
            memo.file_id = data['file_id']
            content_changed = True
            
        if 'folder_id' in data and data['folder_id'] != memo.folder_id:
            memo.folder_id = data['folder_id']
            content_changed = True
            
        if 'relPositionX' in data and data['relPositionX'] != memo.rel_position_x:
            memo.rel_position_x = data['relPositionX']
            content_changed = True
            
        if 'relPositionY' in data and data['relPositionY'] != memo.rel_position_y:
            memo.rel_position_y = data['relPositionY']
            content_changed = True
            
        if 'worldPositionX' in data and data['worldPositionX'] != memo.world_position_x:
            memo.world_position_x = data['worldPositionX']
            content_changed = True
            
        if 'worldPositionY' in data and data['worldPositionY'] != memo.world_position_y:
            memo.world_position_y = data['worldPositionY']
            content_changed = True
            
        if 'worldPositionZ' in data and data['worldPositionZ'] != memo.world_position_z:
            memo.world_position_z = data['worldPositionZ']
            content_changed = True
            
        if 'type' in data and int(data['type']) != memo.type:
            memo.type = int(data['type'])
            content_changed = True
        
        # Update status (this doesn't affect modified_at)
        if 'status' in data:
            memo.status = data['status']
            logger.info(f"Status updated to {memo.status} for memo {id} - modified_at preserved")
        
        # Only update modified_at if content actually changed (not just status)
        if content_changed:
            memo.modified_at = datetime.now(timezone.utc)
            logger.info(f"Content changed for memo {id} - modified_at updated")
        else:
            logger.info(f"Only status/non-content fields changed for memo {id} - modified_at preserved")
        
        db.session.commit()
        logger.info(f"Successfully updated memo with id: {memo.id}")
        return jsonify(memo.to_dict()), 200
    except Exception as e:
        logger.error(f"Error updating memo: {str(e)}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@api_memo_bp.route('/<int:id>', methods=['DELETE'])
def delete_memo(id):
    memo = MemoData.query.get_or_404(id)
    db.session.delete(memo)
    db.session.commit()
    return '', 204 


# 🔹 GET /leaning/memo_rank API 메모 랭킹 조회    
@api_memo_bp.route('/memo_rank', methods=['GET'])
@jwt_required(locations=['headers','cookies'])  # 🔹 JWT 검증을 먼저 수행
def memo_rank():
    from services.user_summary_service import get_period_value
    try:
        filter_type = request.args.get('filter_type', 'all')
        filter_value = request.args.get('filter_value')
        period_type = request.args.get('period_type', 'year')
        period_value = request.args.get('period_value')
        
        if not period_type or not period_value:
            return jsonify({'error': 'Please provide scope, period_type, and period_value'}), 400
        
        start_dt, end_dt = get_period_value(period_type, period_value)
        local_tz = datetime.now().astimezone().tzinfo
        utc_start_dt = datetime.combine(start_dt, time.min, tzinfo=local_tz).astimezone(timezone.utc)
        utc_end_dt = datetime.combine(end_dt, time.max, tzinfo=local_tz).astimezone(timezone.utc)                  
        
        base_query = """
            SELECT m.file_id AS item, COUNT(*) AS cnt, f.name AS name, d.name AS folder_name, ch.name AS channel_name, MAX(m.modified_at) AS modified_at
            FROM memos m
            JOIN users u ON m.user_id = u.id
            JOIN content_rel_pages f ON m.file_id = f.id
            JOIN content_rel_folders d ON f.folder_id = d.id
            JOIN content_rel_channels ch ON d.channel_id = ch.id
            WHERE m.modified_at BETWEEN :start_date AND :end_date AND m.file_id IS NOT NULL AND {filter_clause}
            GROUP BY m.file_id, f.name, d.name, ch.name
            ORDER BY cnt DESC, file_id ASC
            LIMIT 5
            """
        
        params = {
            'start_date': utc_start_dt,
            'end_date': utc_end_dt
        }
        
        if filter_type == 'company':
            filter_clause = "u.company = :filter_value"
            params['filter_value'] = filter_value
        elif filter_type == 'department':
            filter_clause = "u.company = :company AND u.department = :department"
            company, department = filter_value.split('||')
            params['company'] = company
            params['department'] = department
        elif filter_type == 'user':
            filter_clause = "u.id = :filter_value"
            params['filter_value'] = filter_value
        else:
            filter_clause = "1=1"
        
        query = text(base_query.format(filter_clause=filter_clause))
                 
        result = db.session.execute(query, params).mappings().all()
        if not result:
            return jsonify({'error': 'No data found'}), 404
        
        return jsonify({
            'data': [
                {
                    **dict(row),
                    'modified_at': row['modified_at'].isoformat() if isinstance(row['modified_at'], datetime) else row['modified_at']
                }
                for row in result
            ]
            }), 200  # 200: OK
    
    except Exception as e:
        logger.error(f"[memo_rank] error: {str(e)}, {traceback.format_exc()}")
        return jsonify({'[memo_rank] error': str(e)}), 500


# Helper functions for manager detection and status calculation
def is_user_manager_for_memo(user_id, memo_id):
    """Check if user is a manager for the given memo"""
    try:
        memo = MemoData.query.get(memo_id)
        if not memo or not memo.file_id:
            return False
            
        # Check if user has manager permissions for this file
        assignee = Assignees.query.filter_by(user_id=user_id).first()
        if not assignee:
            return False
            
        # Direct file manager
        file_manager = ContentManager.query.filter_by(
            assignee_id=assignee.id,
            type='file',
            file_id=memo.file_id
        ).first()
        
        if file_manager:
            return True
            
        # Check folder-level management
        file_page = ContentRelPages.query.get(memo.file_id)
        if file_page and file_page.folder_id:
            folder_manager = ContentManager.query.filter_by(
                assignee_id=assignee.id,
                type='folder',
                folder_id=file_page.folder_id
            ).first()
            
            if folder_manager:
                return True
                
        return False
    except Exception as e:
        logger.error(f"Error checking manager status: {str(e)}")
        return False


def calculate_memo_status_from_replies(memo_id):
    """Calculate memo status based on last reply author"""
    try:
        memo = MemoData.query.get(memo_id)
        if not memo:
            return 0
            
        # Get the last reply (most recent non-deleted reply)
        last_reply = MemoReply.query.filter_by(
            memo_id=memo_id, 
            is_deleted=False
        ).order_by(desc(MemoReply.created_at)).first()
        
        # If no replies, status is 0 (답변대기)
        if not last_reply:
            return 0
            
        # If last reply is from memo owner, status is 0 (답변대기)
        if last_reply.user_id == memo.user_id:
            return 0
            
        # If last reply is from a manager, status is 1 (답변완료)
        if is_user_manager_for_memo(last_reply.user_id, memo_id):
            return 1
            
        # Otherwise, status is 0 (답변대기) - regular user replied
        return 0
        
    except Exception as e:
        logger.error(f"Error calculating memo status: {str(e)}")
        return 0


@api_memo_bp.route('/<int:memo_id>/is_manager', methods=['GET'])
@jwt_required(locations=['headers','cookies'])
def check_user_is_manager(memo_id):
    """Check if current user is manager for the memo"""
    try:
        current_user_id = get_jwt_identity()
        is_manager = is_user_manager_for_memo(current_user_id, memo_id)
        
        return jsonify({
            "is_manager": is_manager,
            "memo_id": memo_id,
            "user_id": current_user_id
        }), 200
    except Exception as e:
        logger.error(f"Error checking manager status: {str(e)}")
        return jsonify({"error": str(e)}), 500


@api_memo_bp.route('/<int:memo_id>/mark_complete', methods=['POST'])
@jwt_required(locations=['headers','cookies'])
def mark_memo_complete(memo_id):
    """Mark memo as complete (status 2) - manual action by owner or manager"""
    try:
        current_user_id = get_jwt_identity()
        memo = MemoData.query.get_or_404(memo_id)
        
        # Check if user is owner, manager, or SuperAdmin
        is_owner = memo.user_id == current_user_id
        is_manager = is_user_manager_for_memo(current_user_id, memo_id)
        
        # Check if user is SuperAdmin
        user = Users.query.get(current_user_id)
        is_super_admin = user and user.role_id in [1, 2, 999]
        
        if not (is_owner or is_manager or is_super_admin):
            return jsonify({"error": "Only memo owner, manager, or SuperAdmin can mark as complete"}), 403
            
        # Save previous status and mark as complete
        memo.status = 2
        db.session.commit()
        
        logger.info(f"Memo {memo_id} marked as complete by user {current_user_id}")
        
        return jsonify({
            "message": "Memo marked as complete",
            "status": memo.status,
            "memo_id": memo_id
        }), 200
    except Exception as e:
        logger.error(f"Error marking memo as complete: {str(e)}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@api_memo_bp.route('/<int:memo_id>/cancel_complete', methods=['POST'])
@jwt_required(locations=['headers','cookies'])
def cancel_memo_complete(memo_id):
    """Cancel complete status - revert to automatic status based on replies"""
    try:
        current_user_id = get_jwt_identity()
        memo = MemoData.query.get_or_404(memo_id)
        
        # Check if user is owner, manager, or SuperAdmin
        is_owner = memo.user_id == current_user_id
        is_manager = is_user_manager_for_memo(current_user_id, memo_id)
        
        # Check if user is SuperAdmin
        user = Users.query.get(current_user_id)
        is_super_admin = user and user.role_id in [1, 2, 999]
        
        if not (is_owner or is_manager or is_super_admin):
            return jsonify({"error": "Only memo owner, manager, or SuperAdmin can cancel complete"}), 403
            
        # Calculate status based on replies
        new_status = calculate_memo_status_from_replies(memo_id)
        memo.status = new_status
        db.session.commit()
        
        logger.info(f"Memo {memo_id} complete status cancelled by user {current_user_id}, new status: {new_status}")
        
        return jsonify({
            "message": "Complete status cancelled",
            "status": memo.status,
            "memo_id": memo_id
        }), 200
    except Exception as e:
        logger.error(f"Error cancelling memo complete: {str(e)}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

