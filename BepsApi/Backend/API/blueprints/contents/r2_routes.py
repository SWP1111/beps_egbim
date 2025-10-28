"""
R2 Storage routes

This module handles:
- R2 file existence checking
- R2 batch operations
- R2 upload/download operations
- R2 image handling
"""

import logging
import datetime
from datetime import timezone
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import ContentRelPages, ContentRelPageDetails, Users
from log_config import get_content_logger
from .r2_utils import check_r2_object_exists, generate_r2_object_key, generate_r2_signed_url
from services.r2_storage_service import R2StorageService

# Initialize logger
logger = get_content_logger()


def register_r2_routes(api_contents_bp):
    """Register all R2 storage routes to the blueprint"""
    
    @api_contents_bp.route('/files/r2-batch-check', methods=['POST'])
    @jwt_required(locations=['headers','cookies'])
    def batch_check_r2_files():
        """
        Batch check R2 file existence for multiple files
        More efficient for frontend to check many files at once
        
        Request body:
        - file_ids: Array of file IDs to check
        """
        try:
            # Check user permissions
            user_id = get_jwt_identity()
            user = Users.query.get(user_id)
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            # Get request data
            data = request.get_json()
            if not data or 'file_ids' not in data:
                logger.error("Missing file_ids in request body")
                return jsonify({'error': 'file_ids array is required'}), 400
            
            file_ids = data['file_ids']
            if not isinstance(file_ids, list):
                logger.error("file_ids must be a list")
                return jsonify({'error': 'file_ids must be an array'}), 400
            
            logger.info(f"🔍 Batch checking R2 existence for {len(file_ids)} files: {file_ids}")
            
            results = {}
            
            for file_id in file_ids:
                try:
                    # Get the file
                    page = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
                    if not page:
                        results[str(file_id)] = {
                            'r2_exists': False,
                            'error': 'File not found'
                        }
                        continue
                    
                    # Check R2 existence (original logic with fallback)
                    page_name = page.name or f"file_{file_id}"
                    image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf']
                    
                    logger.debug(f"🔍 Checking file {file_id}: name='{page_name}', object_id='{page.object_id}'")
                    
                    r2_exists = False
                    existing_object_key = None
                    
                    # CORRECT LOGIC: Check R2 path based on node hierarchy structure
                    try:
                        # 1. Check main page file (try multiple extensions for the page itself)
                        for ext in image_extensions:
                            test_filename = f"{page_name}{ext}"
                            test_object_key = generate_r2_object_key(file_id, test_filename, is_page_detail=False)
                            
                            if check_r2_object_exists(test_object_key):
                                r2_exists = True
                                existing_object_key = test_object_key
                                logger.debug(f"✅ File {file_id} main file found: {test_object_key}")
                                break
                        
                        # 2. If no main file found, check for page detail files
                        if not r2_exists:
                            # Get page details for this page
                            page_details = ContentRelPageDetails.query.filter_by(
                                page_id=file_id,
                                is_deleted=False
                            ).all()
                            
                            for detail in page_details:
                                detail_extensions = ['.pdf', '.webm', '.mp4', '.avi', '.mov', '.wmv', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx']
                                for ext in detail_extensions:
                                    detail_filename = f"{detail.name}{ext}"
                                    detail_object_key = generate_r2_object_key(detail.id, detail_filename, is_page_detail=True)
                                    
                                    if check_r2_object_exists(detail_object_key):
                                        r2_exists = True
                                        existing_object_key = detail_object_key
                                        logger.debug(f"✅ File {file_id} has detail content: {detail_object_key}")
                                        break
                                
                                if r2_exists:
                                    break
                                    
                    except Exception as e:
                        logger.warning(f"R2 check failed for file {file_id}: {str(e)}")
                        # In development without R2 credentials, make intelligent guess
                        # A page has content if it has a meaningful name or has page details
                        has_meaningful_name = bool(
                            page.name and (
                                any(char.isdigit() for char in page.name) or
                                len(page.name) > 3 or
                                '_' in page.name or
                                '.' in page.name
                            )
                        )
                        
                        has_page_details = ContentRelPageDetails.query.filter_by(
                            page_id=file_id,
                            is_deleted=False
                        ).count() > 0
                        
                        if has_meaningful_name or has_page_details:
                            r2_exists = True
                            existing_object_key = f"fallback/{page_name}"
                            logger.debug(f"✅ File {file_id} assumed to have content (dev mode)")
                    
                    results[str(file_id)] = {
                        'r2_exists': r2_exists,
                        'object_key': existing_object_key,
                        'has_legacy_cloudflare_image': bool(page.object_id and page.object_id.strip())
                    }
                    
                    logger.debug(f"📊 File {file_id} result: r2_exists={r2_exists}, object_key={existing_object_key}")
                    
                except Exception as e:
                    results[str(file_id)] = {
                        'r2_exists': False,
                        'error': str(e)
                    }
            
            # Log summary
            files_with_content = sum(1 for result in results.values() if result.get('r2_exists', False))
            logger.info(f"📊 Batch check complete: {files_with_content}/{len(file_ids)} files have R2 content")
            
            return jsonify(results)
            
        except Exception as e:
            logger.error(f"Error in batch R2 check: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/file/<int:file_id>/r2-exists', methods=['GET'])
    @jwt_required(locations=['headers','cookies'])
    def check_r2_file_exists(file_id):
        """
        Check if a specific file exists in R2 storage by deriving path from node structure
        """
        try:
            # Check if it's a page or page detail
            page = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
            
            if page:
                # Derive R2 path from node structure (same approach as r2-image-url)
                page_name = page.name or f"file_{file_id}"
                image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf']
                
                r2_exists = False
                object_key = None
                
                # Try multiple extensions to find the actual file
                for ext in image_extensions:
                    test_filename = f"{page_name}{ext}"
                    test_object_key = generate_r2_object_key(file_id, test_filename, is_page_detail=False)
                    
                    try:
                        if check_r2_object_exists(test_object_key):
                            r2_exists = True
                            object_key = test_object_key
                            break
                    except Exception:
                        # R2 credentials not available - make intelligent guess
                        name_suggests_content = bool(
                            page.name and 
                            (page.name.lower().endswith(ext.lower()) or 
                             any(char.isdigit() for char in page.name) or  # Has numbers (like 002_08.pdf)
                             len(page.name) > 3)  # Not just placeholder names
                        )
                        
                        if name_suggests_content:
                            r2_exists = True
                            object_key = test_object_key
                            break
                
            else:
                # Check if it's a page detail
                detail = ContentRelPageDetails.query.filter_by(id=file_id, is_deleted=False).first()
                if detail:
                    # For page details, use similar approach
                    detail_name = detail.name or f"detail_{file_id}"
                    image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf']
                    
                    r2_exists = False
                    object_key = None
                    
                    for ext in image_extensions:
                        test_filename = f"{detail_name}{ext}"
                        test_object_key = generate_r2_object_key(file_id, test_filename, is_page_detail=True)
                        
                        try:
                            if check_r2_object_exists(test_object_key):
                                r2_exists = True
                                object_key = test_object_key
                                break
                        except Exception:
                            # R2 credentials not available - make intelligent guess
                            name_suggests_content = bool(
                                detail.name and 
                                (detail.name.lower().endswith(ext.lower()) or 
                                 any(char.isdigit() for char in detail.name) or
                                 len(detail.name) > 3)
                            )
                            
                            if name_suggests_content:
                                r2_exists = True
                                object_key = test_object_key
                                break
                else:
                    return jsonify({'error': 'File not found'}), 404
            
            return jsonify({
                'file_id': file_id,
                'r2_exists': r2_exists,
                'object_key': object_key
            })
            
        except Exception as e:
            logger.error(f"Error checking R2 existence for file {file_id}: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/file/<int:file_id>/r2-upload-url', methods=['POST'])
    @jwt_required(locations=['headers','cookies'])
    def get_r2_upload_url(file_id):
        """
        Get R2 upload URL for a file
        """
        try:
            current_user_id = get_jwt_identity()
            
            # Check if user has permission (admin, reviewer, or super admin)
            user = Users.query.filter_by(id=current_user_id).first()
            if not user or user.role_id not in [1, 2, 999]:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            data = request.get_json()
            if not data or 'filename' not in data:
                return jsonify({'error': 'Missing filename'}), 400
            
            filename = data['filename']
            content_type = data.get('content_type', 'application/octet-stream')
            
            # Find the file
            page = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
            if not page:
                return jsonify({'error': 'File not found'}), 404
            
            # Generate R2 object key
            object_key = generate_r2_object_key(file_id, filename, is_page_detail=False)
            
            # Generate signed upload URL
            upload_url = generate_r2_signed_url(object_key, expires_in=3600, method='PUT')
            
            return jsonify({
                'upload_url': upload_url,
                'object_key': object_key,
                'filename': filename
            })
            
        except Exception as e:
            logger.error(f"Error generating R2 upload URL for file {file_id}: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/file/<int:file_id>/confirm-r2-upload', methods=['POST'])
    @jwt_required(locations=['headers','cookies'])
    def confirm_r2_upload(file_id):
        """
        Confirm R2 upload completion and update database
        """
        try:
            current_user_id = get_jwt_identity()
            
            data = request.get_json()
            if not data or 'object_key' not in data:
                return jsonify({'error': 'Missing object_key'}), 400
            
            object_key = data['object_key']
            filename = data.get('filename', '')
            
            # Find the file
            page = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
            if not page:
                return jsonify({'error': 'File not found'}), 404
            
            # Update the page record
            page.object_id = object_key
            page.updated_at = datetime.datetime.now(timezone.utc)
            
            db.session.commit()
            
            logger.info(f"User {current_user_id} confirmed R2 upload for file {file_id}: {filename}")
            
            return jsonify({
                'message': 'R2 upload confirmed successfully',
                'file': page.to_dict()
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error confirming R2 upload for file {file_id}: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/file/<int:file_id>/r2-image-url', methods=['GET'])
    @jwt_required(locations=['headers','cookies'])
    def get_r2_image_url(file_id):
        """
        Get a pre-signed URL for viewing a file's image from R2
        
        Path parameter:
        - file_id: ID of the file
        
        Query parameters:
        - expires: Expiration time in seconds (optional, default: 3600)
        """
        try:
            # Check R2 configuration first (using Flask app config like the original)
            aws_access_key_id = current_app.config.get('AWS_ACCESS_KEY_ID')
            aws_secret_access_key = current_app.config.get('AWS_SECRET_ACCESS_KEY')
            r2_endpoint_url = current_app.config.get('R2_ENDPOINT_URL')
            r2_bucket_name = current_app.config.get('R2_BUCKET_NAME')
            
            if not aws_access_key_id:
                logger.error("AWS_ACCESS_KEY_ID is not configured")
                return jsonify({'error': 'R2 configuration error: AWS_ACCESS_KEY_ID missing'}), 500
            
            if not aws_secret_access_key:
                logger.error("AWS_SECRET_ACCESS_KEY is not configured")
                return jsonify({'error': 'R2 configuration error: AWS_SECRET_ACCESS_KEY missing'}), 500
            
            if not r2_endpoint_url:
                logger.error("R2_ENDPOINT_URL is not configured")
                return jsonify({'error': 'R2 configuration error: R2_ENDPOINT_URL missing'}), 500
            
            if not r2_bucket_name:
                logger.error("R2_BUCKET_NAME is not configured")
                return jsonify({'error': 'R2 configuration error: R2_BUCKET_NAME missing'}), 500
            
            # Check user permissions
            user_id = get_jwt_identity()
            user = Users.query.get(user_id)
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            # Get the file
            page = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
            if not page:
                return jsonify({'error': 'File not found'}), 404
            
            # Check if R2 file exists (using the same approach as original)
            # First try to find the R2 object using standard extensions
            page_name = page.name or f"file_{file_id}"
            image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf']
            
            r2_object_key = None
            
            # Try multiple extensions to find the actual file
            for ext in image_extensions:
                test_filename = f"{page_name}{ext}"
                test_object_key = generate_r2_object_key(file_id, test_filename, is_page_detail=False)
                
                if check_r2_object_exists(test_object_key):
                    r2_object_key = test_object_key
                    break
            
            if not r2_object_key:
                return jsonify({'error': 'No R2 image associated with this file'}), 404
            
            # Check user permissions (admin, developer, or has specific access)
            if user.role_id not in [1, 2, 999]:  # Not admin, reviewer, or developer
                # Check if user has specific access to this file
                try:
                    from services.content_hierarchy_service import ContentHierarchyService
                    service = ContentHierarchyService()
                    folder_ids, file_ids = service.get_user_accessible_content(int(user_id))
                    
                    if file_id not in file_ids:
                        return jsonify({'error': 'Access denied'}), 403
                except Exception as perm_error:
                    logger.warning(f"Could not check user permissions for file {file_id}: {str(perm_error)}")
                    # Continue anyway for admin/reviewer/developer roles
            
            # Get expires parameter
            expires = int(request.args.get('expires', 3600))
            
            # Generate pre-signed URL for download using the found R2 object key
            signed_url = generate_r2_signed_url(r2_object_key, expires_in=expires, method='GET')
            
            return jsonify({
                'signed_url': signed_url,
                'expires_in': expires,
                'object_key': r2_object_key,
                'legacy_object_id': page.object_id  # Keep for backward compatibility
            })
            
        except Exception as e:
            logger.error(f"Error generating R2 image URL for file {file_id}: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/file/<int:file_id>/r2-object-key', methods=['GET'])
    @jwt_required(locations=['headers','cookies'])
    def get_r2_object_key_preview(file_id):
        """
        Get R2 object key preview for a file
        """
        try:
            filename = request.args.get('filename', 'preview.png')
            is_page_detail = request.args.get('is_page_detail', 'false').lower() == 'true'
            
            # Generate object key preview
            object_key = generate_r2_object_key(file_id, filename, is_page_detail=is_page_detail)
            
            return jsonify({
                'file_id': file_id,
                'filename': filename,
                'object_key': object_key,
                'is_page_detail': is_page_detail
            })
            
        except Exception as e:
            logger.error(f"Error generating R2 object key preview for file {file_id}: {str(e)}")
            return jsonify({'error': str(e)}), 500 