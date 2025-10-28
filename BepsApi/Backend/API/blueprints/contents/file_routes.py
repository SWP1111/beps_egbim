"""
File management routes

This module handles:
- File upload operations
- File download operations  
- File deletion operations
- Basic file management
"""

import logging
import datetime
from datetime import timezone
from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import ContentRelPages, ContentRelFolders, Users
from log_config import get_content_logger
from werkzeug.utils import secure_filename
import uuid

# Initialize logger
logger = get_content_logger()


def register_file_routes(api_contents_bp):
    """Register all file management routes to the blueprint"""
    
    @api_contents_bp.route('/file/<int:file_id>/download', methods=['GET'])
    def download_file(file_id):
        """
        Download a file
        """
        try:
            # Find the file
            file_record = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
            if not file_record:
                return jsonify({'error': 'File not found'}), 404
            
            # For now, return file info (actual file download would need implementation)
            return jsonify({
                'message': f'Download requested for file: {file_record.name}',
                'file_id': file_id,
                'filename': file_record.name
            })
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/file', methods=['POST'])
    @jwt_required(locations=['headers','cookies'])  
    def upload_file():
        """
        Upload a new file
        """
        try:
            current_user_id = get_jwt_identity()
            
            # Check if user has permission (admin, reviewer, or super admin)
            user = Users.query.filter_by(id=current_user_id).first()
            if not user or user.role_id not in [1, 2, 999]:  # 1: admin, 2: reviewer, 999: super admin
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            # Get form data
            channel_id = request.form.get('channelId')
            if not channel_id:
                return jsonify({'error': 'Missing channelId'}), 400
            
            # Check if file was uploaded
            if 'file' not in request.files:
                return jsonify({'error': 'No file uploaded'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            # Create a basic file record (simplified for example)
            filename = secure_filename(file.filename)
            
            # For now, just create a database record
            new_file = ContentRelPages(
                folder_id=None,  # Would need folder logic
                name=filename,
                description=f"Uploaded by {current_user_id}",
                object_id=str(uuid.uuid4()),  # Generate unique object ID
                created_at=datetime.datetime.now(timezone.utc),
                updated_at=datetime.datetime.now(timezone.utc)
            )
            
            db.session.add(new_file)
            db.session.commit()
            
            logger.info(f"User {current_user_id} uploaded file: {filename}")
            
            return jsonify({
                'message': 'File uploaded successfully',
                'file': new_file.to_dict()
            }), 201
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error uploading file: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/files', methods=['DELETE'])
    @jwt_required()
    def delete_files():
        """
        Delete multiple files (soft delete)
        """
        try:
            current_user_id = get_jwt_identity()
            
            # Check if user has permission (admin, reviewer, or super admin)
            user = Users.query.filter_by(id=current_user_id).first()
            if not user or user.role_id not in [1, 2, 999]:  # 1: admin, 2: reviewer, 999: super admin
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            data = request.get_json()
            if not data or 'fileIds' not in data:
                return jsonify({'error': 'Missing fileIds'}), 400
            
            file_ids = data['fileIds']
            if not isinstance(file_ids, list):
                return jsonify({'error': 'fileIds must be a list'}), 400
            
            # Soft delete the files
            deleted_count = 0
            for file_id in file_ids:
                file_record = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
                if file_record:
                    file_record.is_deleted = True
                    file_record.updated_at = datetime.datetime.now(timezone.utc)
                    deleted_count += 1
            
            db.session.commit()
            
            logger.info(f"User {current_user_id} deleted {deleted_count} files")
            
            return jsonify({
                'message': f'Successfully deleted {deleted_count} files',
                'deleted_count': deleted_count
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting files: {str(e)}")
            return jsonify({'error': str(e)}), 500 