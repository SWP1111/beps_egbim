"""
Additional Content routes

This module handles CRUD operations for additional content files:
- List additional content for a page
- Add new additional content (auto-naming, upload to pending)
- Delete additional content
- Get additional content details
"""

import os
import re
import logging
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from extensions import db
from models import PageAdditionals, ContentRelPages, PendingContent
from .permission_middleware import require_upload_permission, get_current_user
from .r2_utils import (
    get_r2_client,
    generate_pending_path,
    check_r2_object_exists,
    delete_r2_object,
    generate_r2_signed_url
)
from log_config import get_content_logger
from flask import current_app

# Initialize logger
logger = get_content_logger()

# Allowed file extensions for additional content
ALLOWED_EXTENSIONS = {
    # Video
    '.mp4', '.avi', '.mkv', '.mov', '.webm', '.asf',
    # Document
    '.pdf',
    # Image
    '.png', '.bmp', '.jpg', '.jpeg', '.gif'
}


def register_additional_content_routes(api_contents_bp):
    """Register all additional content routes to the blueprint"""

    @api_contents_bp.route('/page/<int:page_id>/additionals', methods=['GET'])
    @jwt_required()
    def get_page_additionals(page_id):
        """
        Get list of additional content for a page

        Returns:
            List of additional content with pending status
        """
        try:
            # Verify page exists
            page = ContentRelPages.query.filter_by(id=page_id, is_deleted=False).first()
            if not page:
                return jsonify({'error': 'Page not found'}), 404

            # Get all additional content for this page
            additionals = PageAdditionals.query.filter_by(
                page_id=page_id,
                is_deleted=False
            ).order_by(PageAdditionals.content_number).all()

            result = []
            for additional in additionals:
                # Check if has pending content
                has_pending = PendingContent.query.filter_by(
                    content_type='additional',
                    additional_id=additional.id
                ).first() is not None

                additional_data = additional.to_dict()
                additional_data['has_pending'] = has_pending

                result.append(additional_data)

            return jsonify({
                'page_id': page_id,
                'page_name': page.name,
                'additionals': result,
                'count': len(result)
            })

        except Exception as e:
            logger.error(f"Error getting page additionals: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/page/<int:page_id>/additional', methods=['POST'])
    @jwt_required()
    @require_upload_permission()
    def add_page_additional(page_id):
        """
        Add new additional content for a page

        Process:
        1. Validate file extension
        2. Get next content number (auto-increment)
        3. Generate filename: {page_prefix}_{number}.{ext}
        4. Upload to pending location
        5. Create DB records

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

            # Validate file extension
            _, file_ext = os.path.splitext(file.filename)
            file_ext_lower = file_ext.lower()

            if file_ext_lower not in ALLOWED_EXTENSIONS:
                return jsonify({
                    'error': f'File type {file_ext} not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'
                }), 400

            # Extract page prefix from page name (e.g., "001" from "001_PageName")
            page_name_match = re.match(r'^(\d{3})_', page.name)
            if not page_name_match:
                return jsonify({
                    'error': f'Page name "{page.name}" does not follow naming convention (3-digit prefix required)'
                }), 400

            page_prefix = page_name_match.group(1)

            # Get next content number
            max_number_result = db.session.query(
                db.func.max(PageAdditionals.content_number)
            ).filter_by(page_id=page_id, is_deleted=False).scalar()

            next_number = (max_number_result or 0) + 1

            # Generate new filename
            new_filename = f"{page_prefix}_{next_number:02d}{file_ext_lower}"

            # Generate R2 object key (in original location first, will move to pending)
            # Path: beps-contents/{channel}/{category}/{page}/{filename}
            from .r2_utils import generate_r2_object_key

            # Get page name without extension for folder name
            page_name_no_ext = os.path.splitext(page.name)[0]

            # Build path components
            object_key_base = generate_r2_object_key(page_id, page.name, is_page_detail=False)
            # Remove the page filename from the end
            base_dir = os.path.dirname(object_key_base)
            # Add page folder
            object_key = f"{base_dir}/{page_name_no_ext}/{new_filename}"

            # Generate pending path
            pending_object_key = generate_pending_path(object_key)

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

            logger.info(f"Uploaded additional content to pending: {pending_object_key}")

            # Create PageAdditionals record
            additional = PageAdditionals(
                page_id=page_id,
                filename=new_filename,
                object_key=object_key,  # Store original location (not pending)
                file_extension=file_ext_lower,
                content_number=next_number,
                file_size=file_size
            )
            db.session.add(additional)
            db.session.flush()  # Get ID

            # Create PendingContent record
            user = get_current_user()
            pending = PendingContent(
                content_type='additional',
                page_id=page_id,
                additional_id=additional.id,
                object_key=pending_object_key,
                filename=new_filename,
                file_size=file_size,
                uploaded_by=user.id
            )
            db.session.add(pending)

            db.session.commit()

            return jsonify({
                'message': 'Additional content uploaded to pending successfully',
                'additional': additional.to_dict(),
                'pending': pending.to_dict()
            }), 201

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error adding additional content: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/additional/<int:additional_id>', methods=['DELETE'])
    @jwt_required()
    def delete_additional(additional_id):
        """
        Delete additional content

        Process:
        1. Check permission (실무자 or 책임자)
        2. Delete from R2 (both original and pending if exists)
        3. Delete from DB
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
                return jsonify({
                    'error': '삭제 권한이 없습니다. 이 페이지의 실무자이거나 상위 카테고리의 책임자여야 합니다.'
                }), 403

            # Delete from R2 (original location)
            if additional.object_key:
                delete_r2_object(additional.object_key)

            # Delete pending if exists
            pending = PendingContent.query.filter_by(
                content_type='additional',
                additional_id=additional_id
            ).first()

            if pending:
                if pending.object_key:
                    delete_r2_object(pending.object_key)
                db.session.delete(pending)

            # Mark as deleted in DB
            additional.is_deleted = True
            db.session.commit()

            return jsonify({
                'message': 'Additional content deleted successfully',
                'additional_id': additional_id
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting additional content: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/additional/<int:additional_id>', methods=['GET'])
    @jwt_required()
    def get_additional_details(additional_id):
        """
        Get details for specific additional content

        Returns:
            Additional content info including pending status and signed URL
        """
        try:
            additional = PageAdditionals.query.filter_by(
                id=additional_id,
                is_deleted=False
            ).first()

            if not additional:
                return jsonify({'error': 'Additional content not found'}), 404

            # Check if has pending
            pending = PendingContent.query.filter_by(
                content_type='additional',
                additional_id=additional_id
            ).first()

            result = additional.to_dict()
            result['has_pending'] = pending is not None

            if pending:
                result['pending'] = pending.to_dict()

            # Generate signed URL for download (if exists in R2)
            if check_r2_object_exists(additional.object_key):
                result['download_url'] = generate_r2_signed_url(
                    additional.object_key,
                    expires_in=3600,
                    method='GET'
                )

            return jsonify(result)

        except Exception as e:
            logger.error(f"Error getting additional details: {str(e)}")
            return jsonify({'error': str(e)}), 500
