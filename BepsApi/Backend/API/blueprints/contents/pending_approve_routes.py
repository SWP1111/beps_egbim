"""
Pending Upload and Approve Workflow routes

This module handles:
- Uploading content to pending location
- Checking pending status
- Approving pending content (책임자 only)
- Swapping pending with original and archiving old version
"""

import os
import logging
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from extensions import db
from models import (
    ContentRelPages, PageAdditionals, PendingContent,
    ArchivedContent
)
from .permission_middleware import (
    require_upload_permission,
    require_approve_permission,
    get_current_user
)
from .r2_utils import (
    get_r2_client,
    generate_pending_path,
    generate_archived_path,
    move_r2_object,
    check_r2_object_exists,
    get_r2_object_metadata
)
from log_config import get_content_logger
from flask import current_app

# Initialize logger
logger = get_content_logger()


def register_pending_approve_routes(api_contents_bp):
    """Register all pending/approve workflow routes to the blueprint"""

    @api_contents_bp.route('/page/<int:page_id>/upload-pending', methods=['POST'])
    @jwt_required()
    @require_upload_permission()
    def upload_page_to_pending(page_id):
        """
        Upload page image to pending location

        Process:
        1. Validate file (must be .png)
        2. Upload to pending location
        3. Create PendingContent record

        Request: multipart/form-data with 'file' field
        """
        try:
            # Verify page exists
            page = ContentRelPages.query.filter_by(id=page_id, is_deleted=False).first()
            if not page:
                return jsonify({'error': 'Page not found'}), 404

            # Get uploaded file
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400

            # Validate file extension (must be .png for pages)
            _, file_ext = os.path.splitext(file.filename)
            if file_ext.lower() != '.png':
                return jsonify({'error': 'Page image must be .png format'}), 400

            # Generate R2 object key for original location
            from .r2_utils import generate_r2_object_key
            original_object_key = generate_r2_object_key(page_id, page.name, is_page_detail=False)

            # Generate pending path
            pending_object_key = generate_pending_path(original_object_key)

            # Upload to R2 pending location
            r2_client = get_r2_client()
            bucket_name = current_app.config.get('R2_BUCKET_NAME')

            # Read file data
            file_data = file.read()
            file_size = len(file_data)

            # Validate file size for pages (100MB limit)
            MAX_PAGE_SIZE = 100 * 1024 * 1024  # 100 MB
            if file_size > MAX_PAGE_SIZE:
                return jsonify({
                    'error': f'Page image must be under 100MB. Current size: {file_size / 1024 / 1024:.2f}MB'
                }), 413

            # Upload to pending
            r2_client.put_object(
                Bucket=bucket_name,
                Key=pending_object_key,
                Body=file_data,
                ContentType='image/png'
            )

            logger.info(f"Uploaded page to pending: {pending_object_key}")

            # Delete existing pending if any
            existing_pending = PendingContent.query.filter_by(
                content_type='page',
                page_id=page_id
            ).first()

            if existing_pending:
                db.session.delete(existing_pending)

            # Create PendingContent record
            user = get_current_user()
            pending = PendingContent(
                content_type='page',
                page_id=page_id,
                additional_id=None,
                object_key=pending_object_key,
                filename=page.name,
                file_size=file_size,
                uploaded_by=user.id
            )
            db.session.add(pending)
            db.session.commit()

            return jsonify({
                'message': 'Page uploaded to pending successfully',
                'pending': pending.to_dict()
            }), 201

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error uploading page to pending: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/additional/<int:additional_id>/upload-pending', methods=['POST'])
    @jwt_required()
    def upload_additional_to_pending(additional_id):
        """
        Upload additional content to pending location

        Request: multipart/form-data with 'file' field
        """
        try:
            # Get additional content
            additional = PageAdditionals.query.filter_by(
                id=additional_id,
                is_deleted=False
            ).first()

            if not additional:
                return jsonify({'error': 'Additional content not found'}), 404

            # Check permission
            from .permission_middleware import can_upload_to_page
            user = get_current_user()
            if not user:
                return jsonify({'error': 'Authentication required'}), 401

            if not can_upload_to_page(user.id, additional.page_id):
                return jsonify({'error': '업로드 권한이 없습니다.'}), 403

            # Get uploaded file
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400

            # Validate file extension matches
            _, file_ext = os.path.splitext(file.filename)
            if file_ext.lower() != additional.file_extension:
                return jsonify({
                    'error': f'File extension must match original: {additional.file_extension}'
                }), 400

            # Generate pending path
            pending_object_key = generate_pending_path(additional.object_key)

            # Upload to R2 pending location
            r2_client = get_r2_client()
            bucket_name = current_app.config.get('R2_BUCKET_NAME')

            # Read file data
            file_data = file.read()
            file_size = len(file_data)

            # Upload to pending
            r2_client.put_object(
                Bucket=bucket_name,
                Key=pending_object_key,
                Body=file_data,
                ContentType=file.content_type or 'application/octet-stream'
            )

            logger.info(f"Uploaded additional to pending: {pending_object_key}")

            # Delete existing pending if any
            existing_pending = PendingContent.query.filter_by(
                content_type='additional',
                additional_id=additional_id
            ).first()

            if existing_pending:
                db.session.delete(existing_pending)

            # Create PendingContent record
            pending = PendingContent(
                content_type='additional',
                page_id=additional.page_id,
                additional_id=additional_id,
                object_key=pending_object_key,
                filename=additional.filename,
                file_size=file_size,
                uploaded_by=user.id
            )
            db.session.add(pending)
            db.session.commit()

            return jsonify({
                'message': 'Additional content uploaded to pending successfully',
                'pending': pending.to_dict()
            }), 201

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error uploading additional to pending: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/<content_type>/<int:content_id>/pending-status', methods=['GET'])
    @jwt_required()
    def get_pending_status(content_type, content_id):
        """
        Check if pending content exists

        Args:
            content_type: 'page' or 'additional'
            content_id: page_id or additional_id
        """
        try:
            if content_type not in ['page', 'additional']:
                return jsonify({'error': 'Invalid content_type'}), 400

            # Build query
            query = PendingContent.query.filter_by(content_type=content_type)

            if content_type == 'page':
                query = query.filter_by(page_id=content_id)
            else:  # additional
                query = query.filter_by(additional_id=content_id)

            pending = query.first()

            if pending:
                return jsonify({
                    'has_pending': True,
                    'pending': pending.to_dict()
                })
            else:
                return jsonify({
                    'has_pending': False
                })

        except Exception as e:
            logger.error(f"Error getting pending status: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/page/<int:page_id>/approve-update', methods=['POST'])
    @jwt_required()
    @require_approve_permission()
    def approve_page_update(page_id):
        """
        Approve pending page update (책임자 only)

        Process:
        1. Verify pending content exists
        2. Archive original with timestamp
        3. Move pending to original location
        4. Update DB records
        """
        try:
            # Verify page exists
            page = ContentRelPages.query.filter_by(id=page_id, is_deleted=False).first()
            if not page:
                return jsonify({'error': 'Page not found'}), 404

            # Get pending content
            pending = PendingContent.query.filter_by(
                content_type='page',
                page_id=page_id
            ).first()

            if not pending:
                return jsonify({'error': 'No pending content to approve'}), 404

            # Generate timestamp suffix
            timestamp = datetime.now().strftime('%Y%m%d%H%M')

            # Get original object key
            from .r2_utils import generate_r2_object_key
            original_object_key = generate_r2_object_key(page_id, page.name, is_page_detail=False)

            # Check if original exists (if not, just move pending to original)
            original_exists = check_r2_object_exists(original_object_key)

            r2_client = get_r2_client()
            bucket_name = current_app.config.get('R2_BUCKET_NAME')

            archived_object_key = None
            file_size = 0

            if original_exists:
                # Get original file metadata
                original_metadata = get_r2_object_metadata(original_object_key)
                file_size = original_metadata['size'] if original_metadata else 0

                # Generate archived path
                archived_object_key = generate_archived_path(original_object_key, timestamp)

                # Archive original (copy to archive location)
                move_r2_object(original_object_key, archived_object_key)

                logger.info(f"Archived original: {original_object_key} -> {archived_object_key}")

                # Create ArchivedContent record
                user = get_current_user()
                archived = ArchivedContent(
                    content_type='page',
                    original_page_id=page_id,
                    original_additional_id=None,
                    object_key=archived_object_key,
                    archived_filename=os.path.basename(archived_object_key),
                    file_size=file_size,
                    archived_by=user.id
                )
                db.session.add(archived)

            # Move pending to original location
            move_r2_object(pending.object_key, original_object_key)

            logger.info(f"Moved pending to original: {pending.object_key} -> {original_object_key}")

            # Delete pending record
            db.session.delete(pending)

            # Update page object_id if needed
            if not page.object_id:
                page.object_id = original_object_key

            db.session.commit()

            return jsonify({
                'message': 'Page update approved successfully',
                'archived': archived_object_key if original_exists else None,
                'original': original_object_key
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error approving page update: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/additional/<int:additional_id>/approve-update', methods=['POST'])
    @jwt_required()
    def approve_additional_update(additional_id):
        """
        Approve pending additional content update (책임자 only)

        Process:
        1. Verify pending content exists
        2. Archive original with timestamp
        3. Move pending to original location
        4. Update DB records
        """
        try:
            # Get additional content
            additional = PageAdditionals.query.filter_by(
                id=additional_id,
                is_deleted=False
            ).first()

            if not additional:
                return jsonify({'error': 'Additional content not found'}), 404

            # Check permission (책임자 of category)
            from .permission_middleware import can_approve_update
            user = get_current_user()
            if not user:
                return jsonify({'error': 'Authentication required'}), 401

            if not can_approve_update(user.id, additional.page_id):
                return jsonify({'error': '승인 권한이 없습니다.'}), 403

            # Get pending content
            pending = PendingContent.query.filter_by(
                content_type='additional',
                additional_id=additional_id
            ).first()

            if not pending:
                return jsonify({'error': 'No pending content to approve'}), 404

            # Generate timestamp suffix
            timestamp = datetime.now().strftime('%Y%m%d%H%M')

            # Check if original exists
            original_object_key = additional.object_key
            original_exists = check_r2_object_exists(original_object_key)

            archived_object_key = None
            file_size = 0

            if original_exists:
                # Get original file metadata
                original_metadata = get_r2_object_metadata(original_object_key)
                file_size = original_metadata['size'] if original_metadata else 0

                # Generate archived path
                archived_object_key = generate_archived_path(original_object_key, timestamp)

                # Archive original
                move_r2_object(original_object_key, archived_object_key)

                logger.info(f"Archived original: {original_object_key} -> {archived_object_key}")

                # Create ArchivedContent record
                archived = ArchivedContent(
                    content_type='additional',
                    original_page_id=additional.page_id,
                    original_additional_id=additional_id,
                    object_key=archived_object_key,
                    archived_filename=os.path.basename(archived_object_key),
                    file_size=file_size,
                    archived_by=user.id
                )
                db.session.add(archived)

            # Move pending to original location
            move_r2_object(pending.object_key, original_object_key)

            logger.info(f"Moved pending to original: {pending.object_key} -> {original_object_key}")

            # Update additional file_size
            additional.file_size = pending.file_size

            # Delete pending record
            db.session.delete(pending)

            db.session.commit()

            return jsonify({
                'message': 'Additional content update approved successfully',
                'archived': archived_object_key if original_exists else None,
                'original': original_object_key
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error approving additional update: {str(e)}")
            return jsonify({'error': str(e)}), 500
