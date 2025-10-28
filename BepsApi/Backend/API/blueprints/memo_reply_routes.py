from extensions import db
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import MemoReply, MemoData, Users, MemoReplyAttachment, ContentManager, Assignees, ContentRelPages
from sqlalchemy import desc
import logging
import log_config
from log_config import get_memo_logger, get_content_logger
from datetime import datetime, timezone
import os
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

api_memo_reply_bp = Blueprint('memo_reply', __name__)

# 기존 메모 전용 로거 초기화
logger = get_memo_logger()
# 콘텐츠 로거도 추가 (R2 관련 로깅용)
content_logger = get_content_logger()

@api_memo_reply_bp.route('/', methods=['POST'])
def create_memo_reply():
    try:
        data = request.json
        logger.info(f"Received POST request to /memo/reply with data: {data}")
        
        # Validate required fields
        if not all(key in data for key in ['memo_id', 'user_id', 'content']):
            return jsonify({"error": "Missing required fields"}), 400
            
        # Check if memo exists
        memo = MemoData.query.get(data['memo_id'])
        if not memo:
            return jsonify({"error": "Memo not found"}), 404
            
        # Create new reply
        reply = MemoReply(
            memo_id=data['memo_id'],
            user_id=data['user_id'],
            content=data['content']
        )
        
        # Calculate and update memo status based on reply author
        memo.status = calculate_memo_status_from_replies(memo.id, data['user_id'])
        
        db.session.add(reply)
        db.session.commit()
        
        logger.info(f"Successfully created memo reply with id: {reply.id}, updated memo status to 1")
        return jsonify(reply.to_dict()), 201
    except Exception as e:
        logger.error(f"Error creating memo reply: {str(e)}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@api_memo_reply_bp.route('/memo/<int:memo_id>', methods=['GET'])
def get_replies_by_memo(memo_id):
    try:
        # Check if memo exists
        memo = MemoData.query.get_or_404(memo_id)
        
        # Get replies for this memo that are not deleted, ordered chronologically (oldest first)
        replies = MemoReply.query.filter_by(memo_id=memo_id, is_deleted=False).order_by(MemoReply.created_at.asc()).all()
        
        # The to_dict() method already includes user information through the relationship
        result = [reply.to_dict() for reply in replies]
            
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error retrieving memo replies: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Note: mark_viewed functionality has been replaced with manual status control

@api_memo_reply_bp.route('/memo/<int:memo_id>/debug', methods=['GET'])
@jwt_required(locations=['headers','cookies'])
def debug_memo_status(memo_id):
    try:
        # Get current user from JWT token
        current_user_id = get_jwt_identity()
        
        # Check if memo exists
        memo = MemoData.query.get_or_404(memo_id)
        
        return jsonify({
            "memo_id": memo_id,
            "memo_status": memo.status,
            "memo_author": memo.user_id, 
            "current_user": current_user_id,
            "is_author": memo.user_id == current_user_id,
            "can_change_status": memo.status == 1 and memo.user_id == current_user_id
        }), 200
    except Exception as e:
        logger.error(f"Error debugging memo status: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_memo_reply_bp.route('/<int:id>', methods=['PUT'])
def update_reply(id):
    try:
        reply = MemoReply.query.get_or_404(id)
        data = request.json
        
        # Update content if provided
        if 'content' in data:
            reply.content = data['content']
            
        # Update timestamp
        reply.modified_at = datetime.now(timezone.utc)
        
        db.session.commit()
        logger.info(f"Successfully updated memo reply with id: {reply.id}")
        return jsonify(reply.to_dict()), 200
    except Exception as e:
        logger.error(f"Error updating memo reply: {str(e)}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@api_memo_reply_bp.route('/<int:id>', methods=['DELETE'])
def delete_reply(id):
    try:
        reply = MemoReply.query.get_or_404(id)
        
        # Get memo_id before deletion for status recalculation
        memo_id = reply.memo_id
        
        # Soft delete by setting is_deleted flag
        reply.is_deleted = True
        
        # Recalculate memo status after reply deletion
        memo = MemoData.query.get(memo_id)
        if memo:
            memo.status = calculate_memo_status_from_replies(memo_id)
        
        db.session.commit()
        
        logger.info(f"Successfully deleted memo reply with id: {reply.id}, updated memo status")
        return '', 204
    except Exception as e:
        logger.error(f"Error deleting memo reply: {str(e)}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ======== R2 ATTACHMENT UTILITY FUNCTIONS ========

def get_r2_client():
    """Create and return a configured R2 (S3-compatible) client"""
    try:
        aws_access_key_id = current_app.config.get('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = current_app.config.get('AWS_SECRET_ACCESS_KEY')
        r2_endpoint_url = current_app.config.get('R2_ENDPOINT_URL')
        
        if not aws_access_key_id or not aws_secret_access_key:
            raise ValueError("R2 credentials not found in configuration")
        
        # Configure the client with specific settings for R2
        config = Config(
            signature_version='s3v4',
            retries={'max_attempts': 3},
            s3={
                'addressing_style': 'virtual'  # Use virtual hosted-style requests
            }
        )
        
        client = boto3.client(
            's3',
            endpoint_url=r2_endpoint_url,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name='auto',  # R2 uses 'auto' region
            config=config
        )
        
        return client
    except Exception as e:
        content_logger.error(f"Failed to create R2 client: {str(e)}")
        raise


def generate_r2_signed_url(object_key, expires_in=3600, method='GET', bucket_name=None):
    """Generate a pre-signed URL for R2 object access"""
    try:
        r2_client = get_r2_client()
        
        # Use provided bucket name or default to LFS bucket for attachments
        if bucket_name is None:
            bucket_name = current_app.config.get('R2_LFS_BUCKET_NAME', 'beps-lfs')
        
        if not bucket_name:
            raise ValueError("R2 bucket name not found in configuration")
        
        # Generate signed URL
        if method.upper() == 'GET':
            signed_url = r2_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': object_key},
                ExpiresIn=expires_in
            )
        elif method.upper() == 'PUT':
            signed_url = r2_client.generate_presigned_url(
                'put_object',
                Params={'Bucket': bucket_name, 'Key': object_key},
                ExpiresIn=expires_in
            )
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        return signed_url
    except Exception as e:
        content_logger.error(f"Failed to generate R2 signed URL: {str(e)}")
        raise


def generate_attachment_object_key(reply_id, filename):
    """Generate R2 object key for memo reply attachment"""
    try:
        # Get reply to get the created date
        reply = MemoReply.query.get(reply_id)
        if not reply:
            raise ValueError(f"Reply {reply_id} not found")
        
        # Use reply creation date for folder structure
        reply_date = reply.created_at
        year = reply_date.strftime('%Y')
        month = reply_date.strftime('%m')
        day = reply_date.strftime('%d')
        
        # Sanitize filename
        safe_filename = os.path.basename(filename)
        
        # Generate object key: opinion-reply-attachment/YYYY/MM/DD/{reply-id}/{filename}
        # Note: bucket name is beps-lfs, so we don't include it in the object key
        object_key = f"opinion-reply-attachment/{year}/{month}/{day}/{reply_id}/{safe_filename}"
        
        return object_key
    except Exception as e:
        content_logger.error(f"Failed to generate attachment object key: {str(e)}")
        raise


def check_r2_object_exists(object_key, bucket_name=None):
    """Check if an object exists in R2 storage"""
    try:
        r2_client = get_r2_client()
        
        # Use provided bucket name or default to LFS bucket for attachments
        if bucket_name is None:
            bucket_name = current_app.config.get('R2_LFS_BUCKET_NAME', 'beps-lfs')
        
        r2_client.head_object(Bucket=bucket_name, Key=object_key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        else:
            content_logger.error(f"Error checking R2 object existence: {str(e)}")
            raise
    except Exception as e:
        content_logger.error(f"Failed to check R2 object existence: {str(e)}")
        raise


# ======== ATTACHMENT API ENDPOINTS ========

@api_memo_reply_bp.route('/<int:reply_id>/attachment/upload-url', methods=['POST'])
@jwt_required(locations=['headers','cookies'])
def get_attachment_upload_url(reply_id):
    """Get R2 upload URL for memo reply attachment"""
    try:
        current_user_id = get_jwt_identity()
        
        # Check if reply exists
        reply = MemoReply.query.filter_by(id=reply_id, is_deleted=False).first()
        if not reply:
            return jsonify({'error': 'Reply not found'}), 404
        
        # Only allow the reply author to add attachments
        if reply.user_id != current_user_id:
            return jsonify({'error': 'Only reply author can add attachments'}), 403
        
        # Get request data
        data = request.get_json()
        if not data or 'filename' not in data:
            return jsonify({'error': 'Missing filename'}), 400
        
        filename = data['filename']
        content_type = data.get('content_type', 'application/octet-stream')
        file_size = data.get('file_size', 0)
        
        # Validate file type (allow images primarily)
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf', '.doc', '.docx', '.txt'}
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in allowed_extensions:
            return jsonify({'error': f'Invalid file type {file_ext}. Allowed types: {", ".join(allowed_extensions)}'}), 400
        
        # Validate file size (50MB limit for attachments)
        if file_size > 50 * 1024 * 1024:  # 50MB
            return jsonify({'error': 'File size too large. Maximum 50MB allowed.'}), 400
        
        # Generate object key
        object_key = generate_attachment_object_key(reply_id, filename)
        
        # Generate signed upload URL
        upload_url = generate_r2_signed_url(object_key, expires_in=1800, method='PUT')  # 30 minutes
        
        return jsonify({
            'upload_url': upload_url,
            'object_key': object_key,
            'reply_id': reply_id,
            'filename': filename,
            'expires_in': 1800
        })
        
    except Exception as e:
        content_logger.error(f"Error generating attachment upload URL for reply {reply_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500


@api_memo_reply_bp.route('/<int:reply_id>/attachment/confirm-upload', methods=['POST'])
@jwt_required(locations=['headers','cookies'])
def confirm_attachment_upload(reply_id):
    """Confirm attachment upload and save to database"""
    try:
        current_user_id = get_jwt_identity()
        
        # Check if reply exists and user has permission
        reply = MemoReply.query.filter_by(id=reply_id, is_deleted=False).first()
        if not reply:
            return jsonify({'error': 'Reply not found'}), 404
        
        if reply.user_id != current_user_id:
            return jsonify({'error': 'Only reply author can add attachments'}), 403
        
        # Get request data
        data = request.get_json()
        if not data or 'object_key' not in data or 'filename' not in data:
            return jsonify({'error': 'Missing object_key or filename'}), 400
        
        object_key = data['object_key']
        filename = data['filename']
        content_type = data.get('content_type', 'application/octet-stream')
        file_size = data.get('file_size', 0)
        
        # Verify the object exists in R2
        if not check_r2_object_exists(object_key):
            return jsonify({'error': 'Object not found in R2 storage'}), 404
        
        # Create attachment record
        attachment = MemoReplyAttachment(
            memo_reply_id=reply_id,
            filename=filename,
            object_key=object_key,
            file_size=file_size,
            content_type=content_type
        )
        
        db.session.add(attachment)
        db.session.commit()
        
        content_logger.info(f"User {current_user_id} uploaded attachment for reply {reply_id}: {filename}")
        
        return jsonify({
            'message': 'Attachment uploaded successfully',
            'attachment': attachment.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        content_logger.error(f"Error confirming attachment upload for reply {reply_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500


@api_memo_reply_bp.route('/attachment/<int:attachment_id>/url', methods=['GET'])
@jwt_required(locations=['headers','cookies'])
def get_attachment_url(attachment_id):
    """Get signed URL for viewing attachment"""
    try:
        # Check if attachment exists
        attachment = MemoReplyAttachment.query.get_or_404(attachment_id)
        
        # Check if related reply exists and is not deleted
        reply = MemoReply.query.filter_by(id=attachment.memo_reply_id, is_deleted=False).first()
        if not reply:
            return jsonify({'error': 'Related reply not found'}), 404
        
        # Get expires parameter
        expires = int(request.args.get('expires', 3600))
        
        # Generate signed URL for viewing
        signed_url = generate_r2_signed_url(attachment.object_key, expires_in=expires, method='GET')
        
        return jsonify({
            'signed_url': signed_url,
            'filename': attachment.filename,
            'content_type': attachment.content_type,
            'file_size': attachment.file_size,
            'expires_in': expires
        })
        
    except Exception as e:
        content_logger.error(f"Error generating attachment URL for attachment {attachment_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500


@api_memo_reply_bp.route('/attachment/<int:attachment_id>', methods=['DELETE'])
@jwt_required(locations=['headers','cookies'])
def delete_attachment(attachment_id):
    """Delete attachment"""
    try:
        current_user_id = get_jwt_identity()
        
        # Check if attachment exists
        attachment = MemoReplyAttachment.query.get_or_404(attachment_id)
        
        # Check if related reply exists and user has permission
        reply = MemoReply.query.filter_by(id=attachment.memo_reply_id, is_deleted=False).first()
        if not reply:
            return jsonify({'error': 'Related reply not found'}), 404
        
        if reply.user_id != current_user_id:
            return jsonify({'error': 'Only reply author can delete attachments'}), 403
        
        # Delete from database
        db.session.delete(attachment)
        db.session.commit()
        
        # Note: We're not deleting from R2 storage for now to avoid data loss
        # This can be implemented later with a cleanup job
        
        content_logger.info(f"User {current_user_id} deleted attachment {attachment_id}")
        
        return '', 204
        
    except Exception as e:
        db.session.rollback()
        content_logger.error(f"Error deleting attachment {attachment_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500


# Helper functions for status calculation
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


def calculate_memo_status_from_replies(memo_id, new_reply_user_id=None):
    """Calculate memo status based on replies, optionally considering a new reply"""
    try:
        memo = MemoData.query.get(memo_id)
        if not memo:
            return 0
            
        # If this is being called for a new reply, consider that user as the last replier
        if new_reply_user_id:
            last_reply_user_id = new_reply_user_id
        else:
            # Get the last reply (most recent non-deleted reply by creation time)
            last_reply = MemoReply.query.filter_by(
                memo_id=memo_id, 
                is_deleted=False
            ).order_by(desc(MemoReply.created_at)).first()
            
            # If no replies, status is 0 (답변대기)
            if not last_reply:
                return 0
                
            last_reply_user_id = last_reply.user_id
            
        # If last reply is from memo owner, status is 0 (답변대기)
        if last_reply_user_id == memo.user_id:
            return 0
            
        # If last reply is from a manager, status is 1 (답변완료)
        if is_user_manager_for_memo(last_reply_user_id, memo_id):
            return 1
        
        # If last reply is from a SuperAdmin, status is 1 (답변완료)
        user = Users.query.get(last_reply_user_id)
        if user and user.role_id in [1, 2, 999]:  # SuperAdmin roles
            return 1
            
        # Otherwise, status is 0 (답변대기) - regular user replied
        return 0
        
    except Exception as e:
        logger.error(f"Error calculating memo status: {str(e)}")
        return 0
