"""
Page Detail routes

This module handles:
- Page detail content upload
- Page detail content download
- Page detail specific operations
"""

import logging
import datetime
from datetime import timezone
from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import ContentRelPageDetails, ContentRelPages, Users
from log_config import get_content_logger
from werkzeug.utils import secure_filename
from .r2_utils import generate_r2_object_key, generate_r2_signed_url
import uuid

# Initialize logger
logger = get_content_logger()


def register_page_detail_routes(api_contents_bp):
    """Register all page detail routes to the blueprint"""
    
    @api_contents_bp.route('/page-detail/<int:detail_id>/upload-content', methods=['POST'])
    @jwt_required(locations=['headers','cookies'])
    def upload_page_detail_content(detail_id):
        """
        Upload content for a page detail
        """
        try:
            current_user_id = get_jwt_identity()
            
            # Check if user has permission (admin, reviewer, or super admin)
            user = Users.query.filter_by(id=current_user_id).first()
            if not user or user.role_id not in [1, 2, 999]:  # 1: admin, 2: reviewer, 999: super admin
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            # Find the page detail
            detail = ContentRelPageDetails.query.filter_by(id=detail_id, is_deleted=False).first()
            if not detail:
                return jsonify({'error': 'Page detail not found'}), 404
            
            # Check if file was uploaded
            if 'file' not in request.files:
                return jsonify({'error': 'No file uploaded'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            # Generate object key for R2 storage
            filename = secure_filename(file.filename)
            object_key = generate_r2_object_key(detail_id, filename, is_page_detail=True)
            
            # Update the detail record
            detail.object_id = object_key
            detail.updated_at = datetime.datetime.now(timezone.utc)
            
            db.session.commit()
            
            logger.info(f"User {current_user_id} uploaded content for page detail {detail_id}: {filename}")
            
            return jsonify({
                'message': 'Page detail content uploaded successfully',
                'detail': detail.to_dict()
            }), 201
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error uploading page detail content: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/page-detail/<int:detail_id>/download', methods=['GET'])
    @jwt_required(locations=['headers','cookies'])
    def download_page_detail(detail_id):
        """
        Download page detail content
        """
        try:
            # Find the page detail
            detail = ContentRelPageDetails.query.filter_by(id=detail_id, is_deleted=False).first()
            if not detail:
                return jsonify({'error': 'Page detail not found'}), 404
            
            if not detail.object_id:
                return jsonify({'error': 'No content available for this page detail'}), 404
            
            # Generate signed URL for download
            try:
                signed_url = generate_r2_signed_url(detail.object_id, expires_in=3600, method='GET')
                
                # For now, return the signed URL (in production, you might want to proxy the download)
                return jsonify({
                    'download_url': signed_url,
                    'filename': detail.name,
                    'detail_id': detail_id
                })
                
            except Exception as e:
                logger.error(f"Error generating download URL for page detail {detail_id}: {str(e)}")
                return jsonify({'error': 'Failed to generate download URL'}), 500
            
        except Exception as e:
            logger.error(f"Error downloading page detail {detail_id}: {str(e)}")
            return jsonify({'error': str(e)}), 500 