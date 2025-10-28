import os
import logging
import log_config
from log_config import get_content_logger
from flask import Blueprint, jsonify, request, send_file, current_app
import datetime
from datetime import timezone
from datetime import timedelta
from extensions import db
from models import ContentRelPages, ContentRelFolders, ContentRelChannels, ContentRelPageDetails, Users, ContentManager
from sqlalchemy.exc import OperationalError
from sqlalchemy.sql import text
import re
import urllib.parse
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.content_hierarchy_service import ContentHierarchyService
from werkzeug.utils import secure_filename
import uuid
import hmac
import hashlib
import time
import requests
import json
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError, NoCredentialsError

api_contents_bp = Blueprint('contents', __name__) # 콘텐츠 블루프린트 생성

# 콘텐츠용 로거 초기화
logger = get_content_logger()


@api_contents_bp.route('/file/get_detailed_path', methods=['GET'])
def get_detailed_path():
    """Build a detailed path from ContentRel tables using file_id"""
    file_id = request.args.get('file_id')
    
    if not file_id:
        return jsonify({'error': 'Missing file_id parameter'}), 400
    
    try:
        # Start with the file - check if it's a page or page detail
        page = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
        
        # Stack to build the path
        path_components = []
        
        if page:
            # This is a page
            path_components.append(page.name)
            folder_id = page.folder_id
        else:
            # Check if it's a page detail
            detail = ContentRelPageDetails.query.filter_by(id=file_id, is_deleted=False).first()
            if detail:
                path_components.append(detail.name)
                # Get the parent page
                parent_page = ContentRelPages.query.filter_by(id=detail.page_id, is_deleted=False).first()
                if parent_page:
                    path_components.append(parent_page.name)
                    folder_id = parent_page.folder_id
                else:
                    return jsonify({'error': 'Parent page not found'}), 404
            else:
                return jsonify({'error': 'File not found in content tables'}), 404
        
        # Traverse the folder hierarchy
        while folder_id is not None:
            folder = ContentRelFolders.query.filter_by(id=folder_id, is_deleted=False).first()
            if not folder:
                break
            
            path_components.append(folder.name)
            
            if folder.parent_id is None:
                # Top-level folder, get the channel
                channel = ContentRelChannels.query.filter_by(id=folder.channel_id, is_deleted=False).first()
                if channel:
                    path_components.append(channel.name)
                break
            
            folder_id = folder.parent_id
        
        # Reverse the path components to build the path
        path_components.reverse()
        full_path = '/'.join(path_components)
        
        return jsonify({
            'detailed_path': full_path
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/channel/children', methods=['GET'])
def get_channel_child():
    """
    Get all top-level folders for a given channel
    
    Returns a list of folder IDs that have parent_id=null and belong to the given channel_id
    """
    try:
        channel_id = request.args.get('channel_id')
        if not channel_id:
            return jsonify({'error': 'Missing channel_id parameter'}), 400
            
        # Use the hierarchy service
        service = ContentHierarchyService()
        folder_ids = service.get_channel_children(int(channel_id))
        
        return jsonify({
            'folder_ids': folder_ids,
            'count': len(folder_ids)
        })
    except Exception as e:
        logger.error(f"Error in get_channel_child: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/folder/children', methods=['GET'])
def get_folder_child():
    """
    Get all subfolders or pages within a given folder
    
    If there are subfolders, returns those IDs and sets isLeafFolder=false
    If there are no subfolders, returns page IDs and sets isLeafFolder=true
    """
    try:
        folder_id = request.args.get('folder_id')
        if not folder_id:
            return jsonify({'error': 'Missing folder_id parameter'}), 400
            
        # Use the hierarchy service
        service = ContentHierarchyService()
        child_ids, is_leaf_folder = service.get_folder_children(int(folder_id))
        
        response_data = {
            'is_leaf_folder': is_leaf_folder,
            'count': len(child_ids)
        }
        
        # Set the correct field based on whether this is a leaf folder
        if is_leaf_folder:
            response_data['page_ids'] = child_ids
        else:
            response_data['folder_ids'] = child_ids
        
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error in get_folder_child: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/hierarchy', methods=['GET'])
def get_content_hierarchy():
    """
    Get the full content hierarchy (channels, folders, and pages)
    
    Optional query parameters:
    - refresh: If true, rebuilds the hierarchy instead of using cache
    - format: 'full' (default) or 'summary' 
    """
    try:
        # Check if we should bypass cache
        refresh = request.args.get('refresh', 'false').lower() == 'true'
        
        # Get hierarchy
        service = ContentHierarchyService()
        hierarchy = service.get_full_hierarchy(use_cache=not refresh)
        
        return jsonify(hierarchy)
    except Exception as e:
        logger.error(f"Error getting content hierarchy: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/file/<int:file_id>/path', methods=['GET'])
def get_file_path(file_id):
    """
    Get the complete path to a specific file
    
    Returns the full path information including all components and IDs
    """
    try:
        service = ContentHierarchyService()
        path_info = service.get_file_path(file_id)
        
        if not path_info:
            return jsonify({'error': 'File not found'}), 404
            
        return jsonify(path_info)
    except Exception as e:
        logger.error(f"Error getting file path: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ?�로??API ?�드?�인??추�?

@api_contents_bp.route('/channels', methods=['GET'])
def get_channels():
    """
    Get all channels
    
    Returns a list of all available channels
    """
    try:
        service = ContentHierarchyService()
        channels = service.get_channels()
        
        return jsonify({
            'channels': channels
        })
    except Exception as e:
        logger.error(f"Error getting channels: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/hierarchy/channel/<int:channel_id>', methods=['GET'])
def get_channel_hierarchy(channel_id):
    """
    Get the hierarchy for a specific channel
    
    Returns folders and files for the given channel, with optional filtering
    
    Query parameters:
    - filters: JSON encoded filter configuration
    """
    try:
        # Get filter parameters
        filters_json = request.args.get('filters', '{}')
        try:
            import json
            filters = json.loads(filters_json)
        except:
            filters = {'all': True}
        
        service = ContentHierarchyService()
        hierarchy = service.get_channel_hierarchy(channel_id, filters)
        
        return jsonify(hierarchy)
    except Exception as e:
        logger.error(f"Error getting channel hierarchy: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/user-accessible', methods=['GET'])
def get_user_accessible_content():
    """
    Get content that is accessible to a specific user
    
    Returns lists of folder_ids and file_ids that the user has access to
    
    Query parameters:
    - user_id: ID of the user to check access for
    """
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': 'Missing user_id parameter'}), 400
        
        service = ContentHierarchyService()
        folder_ids, file_ids = service.get_user_accessible_content(int(user_id))
        
        return jsonify({
            'folderIds': folder_ids,
            'fileIds': file_ids
        })
    except Exception as e:
        logger.error(f"Error getting user accessible content: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/channel/<int:channel_id>/check-accessibility', methods=['GET'])
def check_channel_accessibility(channel_id):
    """
    Check if a channel contains any content accessible to a user
    
    Returns a boolean indicating if the user has access to anything in the channel
    
    Query parameters:
    - user_id: ID of the user to check access for
    """
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': 'Missing user_id parameter'}), 400
        
        service = ContentHierarchyService()
        has_accessible_content = service.channel_has_accessible_content(channel_id, int(user_id))
        
        return jsonify({
            'has_accessible_content': has_accessible_content
        })
    except Exception as e:
        logger.error(f"Error checking channel accessibility: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/file/<int:file_id>/download', methods=['GET'])
def download_file(file_id):
    """
    Download a file
    
    Returns the file for download
    """
    try:
        service = ContentHierarchyService()
        file_path, filename = service.get_file_download_info(file_id)
        
        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'File not found or not available for download'}), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/channel', methods=['POST'])
@jwt_required(locations=['headers','cookies'])
def create_channel():
    """
    Create a new channel
    
    Requires admin or developer role
    
    Request body:
    - name: Name of the channel
    """
    try:
        # Check user role for permission
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user or (user.role_id not in [1, 999]):  # 1=admin, 999=developer
            return jsonify({'error': 'Permission denied. Admin role required.'}), 403
        
        # Get request data
        request_data = request.json
        if not request_data or 'name' not in request_data:
            return jsonify({'error': 'Channel name is required'}), 400
        
        # Create channel
        service = ContentHierarchyService()
        channel_id = service.create_channel(request_data['name'], user_id)
        
        # Clear cache for hierarchy
        service.clear_hierarchy_cache()
        
        return jsonify({
            'message': 'Channel created successfully',
            'channel_id': channel_id
        })
    except Exception as e:
        logger.error(f"Error creating channel: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/channel/<int:channel_id>', methods=['DELETE'])
@jwt_required(locations=['headers','cookies'])
def delete_channel(channel_id):
    """
    Delete a channel
    
    Requires admin or developer role
    """
    try:
        # Check user role for permission
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user or (user.role_id not in [1, 999]):  # 1=admin, 999=developer
            return jsonify({'error': 'Permission denied. Admin role required.'}), 403
        
        # Delete channel
        service = ContentHierarchyService()
        success = service.delete_channel(channel_id, user_id)
        
        if not success:
            return jsonify({'error': 'Channel not found or could not be deleted'}), 404
        
        # Clear cache for hierarchy
        service.clear_hierarchy_cache()
        
        return jsonify({
            'message': 'Channel deleted successfully'
        })
    except Exception as e:
        logger.error(f"Error deleting channel: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/file', methods=['POST'])
@jwt_required(locations=['headers','cookies'])  
def upload_file():
    """
    Upload a file to a channel or folder
    
    Requires admin, developer, or reviewer role
    
    Form data:
    - file: The file to upload
    - channelId: Channel ID
    - folderId: (Optional) Folder ID
    - name: (Optional) Name for the file, defaults to filename
    - version: (Optional) Version of the file
    """
    try:
        # Check user role for permission
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user or (user.role_id not in [1, 2, 999]):  # 1=admin, 2=reviewer, 999=developer
            return jsonify({'error': 'Permission denied. Admin or reviewer role required.'}), 403
        
        # Check if file is included
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in the request'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        # Get other form data
        channel_id = request.form.get('channelId')
        if not channel_id:
            return jsonify({'error': 'Channel ID is required'}), 400
        
        folder_id = request.form.get('folderId', None)
        name = request.form.get('name', None) or file.filename
        version = request.form.get('version', '1.0')
        
        # Save file
        filename = secure_filename(file.filename)
        temp_dir = current_app.config.get('UPLOAD_FOLDER', '/tmp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Generate unique filename
        file_uuid = str(uuid.uuid4())
        temp_path = os.path.join(temp_dir, f"{file_uuid}_{filename}")
        file.save(temp_path)
        
        # Add to database
        service = ContentHierarchyService()
        file_id = service.add_file(
            temp_path,
            name,
            int(channel_id),
            folder_id=int(folder_id) if folder_id else None,
            version=version,
            user_id=user_id
        )
        
        # Clear cache for hierarchy
        service.clear_hierarchy_cache()
        
        return jsonify({
            'message': 'File uploaded successfully',
            'file_id': file_id
        })
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/files', methods=['DELETE'])
@jwt_required()
def delete_files():
    """
    Delete one or more files
    
    Requires admin, developer, or reviewer role
    
    Request body:
    - fileIds: Array of file IDs to delete
    """
    try:
        # Check user role for permission
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user or (user.role_id not in [1, 2, 999]):  # 1=admin, 2=reviewer, 999=developer
            return jsonify({'error': 'Permission denied. Admin or reviewer role required.'}), 403
        
        # Get request data
        request_data = request.json
        if not request_data or 'fileIds' not in request_data or not request_data['fileIds']:
            return jsonify({'error': 'File IDs are required'}), 400
        
        # Delete files
        service = ContentHierarchyService()
        success, failed = service.delete_files(request_data['fileIds'], user_id)
        
        # Clear cache for hierarchy
        service.clear_hierarchy_cache()
        
        if failed:
            return jsonify({
                'message': f'Some files could not be deleted',
                'success': success,
                'failed': failed
            }), 207  # Multi-Status
        
        return jsonify({
            'message': 'Files deleted successfully',
            'count': len(success)
        })
    except Exception as e:
        logger.error(f"Error deleting files: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/folder', methods=['POST'])
@jwt_required(locations=['headers','cookies'])
def create_folder():
    """
    Create a new folder
    
    Requires admin, developer, or reviewer role
    
    Request body:
    - name: Name of the folder
    - channelId: Channel ID
    - parentId: (Optional) Parent folder ID
    """
    try:
        # Check user role for permission
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user or (user.role_id not in [1, 2, 999]):  # 1=admin, 2=reviewer, 999=developer
            return jsonify({'error': 'Permission denied. Admin or reviewer role required.'}), 403
        
        # Get request data
        request_data = request.json
        if not request_data:
            return jsonify({'error': 'Request body is required'}), 400
        
        if 'name' not in request_data:
            return jsonify({'error': 'Folder name is required'}), 400
            
        if 'channelId' not in request_data:
            return jsonify({'error': 'Channel ID is required'}), 400
        
        parent_id = request_data.get('parentId', None)
        
        # Create folder
        service = ContentHierarchyService()
        folder_id = service.create_folder(
            request_data['name'],
            int(request_data['channelId']),
            parent_id=int(parent_id) if parent_id else None,
            user_id=user_id
        )
        
        # Clear cache for hierarchy
        service.clear_hierarchy_cache()
        
        return jsonify({
            'message': 'Folder created successfully',
            'folder_id': folder_id
        })
    except Exception as e:
        logger.error(f"Error creating folder: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/folder/<int:folder_id>', methods=['DELETE'])
@jwt_required(locations=['headers','cookies'])
def delete_folder(folder_id):
    """
    Delete a folder and its contents
    
    Requires admin or developer role
    """
    try:
        # Check user role for permission
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user or (user.role_id not in [1, 999]):  # 1=admin, 999=developer
            return jsonify({'error': 'Permission denied. Admin role required.'}), 403
        
        # Delete folder
        service = ContentHierarchyService()
        success = service.delete_folder(folder_id, user_id)
        
        if not success:
            return jsonify({'error': 'Folder not found or could not be deleted'}), 404
        
        # Clear cache for hierarchy
        service.clear_hierarchy_cache()
        
        return jsonify({
            'message': 'Folder deleted successfully'
        })
    except Exception as e:
        logger.error(f"Error deleting folder: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/content_manager', methods=['GET'])
def get_content_managers():
    """
    Get all content managers
    
    Returns a list of content manager entries
    """
    try:
        managers = ContentManager.query.all()
        return jsonify([manager.to_dict() for manager in managers])
    except Exception as e:
        logger.error(f"Error getting content managers: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/content_manager', methods=['POST'])
def add_content_manager():
    """
    Add a new content manager entry
    
    Request body:
    - user_id: ID of the user to add as manager
    - type: Type of permission ('channel', 'folder', or 'file')
    - file_id: ID of the file (when type is 'file')
    - folder_id: ID of the folder (when type is 'folder')
    - channel_id: ID of the channel (when type is 'channel')
    """
    try:
        data = request.json
        
        if not data or 'user_id' not in data or 'type' not in data:
            return jsonify({'error': 'Required fields missing: user_id and type'}), 400
        
        user_id = data['user_id']
        permission_type = data['type']
        
        # Validate user exists - use case insensitive search
        user = Users.query.filter(Users.id.ilike(user_id)).first()
        if not user:
            return jsonify({'error': f'User with ID {user_id} not found'}), 404
        
        # Use the actual user ID from the database to ensure consistent casing
        user_id = user.id
        
        # Check for duplicate permission based on type
        if permission_type == 'channel' and 'channel_id' in data:
            channel_id = int(data['channel_id'])
            
            # Verify channel exists
            channel = ContentRelChannels.query.filter_by(id=channel_id, is_deleted=False).first()
            if not channel:
                return jsonify({'error': f'Channel with ID {channel_id} not found'}), 404
            
            # Check for duplicate
            duplicate = ContentManager.query.filter_by(
                user_id=user_id,
                type='channel',
                channel_id=channel_id
            ).first()
            
            if duplicate:
                return jsonify({'error': f'User {user_id} already has channel manager permission for this channel'}), 409
            
            # Create new manager entry
            manager = ContentManager(
                user_id=user_id,
                type=permission_type,
                channel_id=channel_id
            )
        
        elif permission_type == 'folder' and 'folder_id' in data:
            folder_id = int(data['folder_id'])
            
            # Verify folder exists
            folder = ContentRelFolders.query.filter_by(id=folder_id, is_deleted=False).first()
            if not folder:
                return jsonify({'error': f'Folder with ID {folder_id} not found'}), 404
            
            # Check for duplicate
            duplicate = ContentManager.query.filter_by(
                user_id=user_id,
                type='folder',
                folder_id=folder_id
            ).first()
            
            if duplicate:
                return jsonify({'error': f'User {user_id} already has folder manager permission for this folder'}), 409
            
            # Create new manager entry
            manager = ContentManager(
                user_id=user_id,
                type=permission_type,
                folder_id=folder_id
            )
        
        elif permission_type == 'file' and 'file_id' in data:
            file_id = int(data['file_id'])
            
            # Verify file exists
            file = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
            if not file:
                return jsonify({'error': f'File with ID {file_id} not found'}), 404
            
            # Check for duplicate
            duplicate = ContentManager.query.filter_by(
                user_id=user_id,
                type='file',
                file_id=file_id
            ).first()
            
            if duplicate:
                return jsonify({'error': f'User {user_id} already has file manager permission for this file'}), 409
            
            # Create new manager entry
            manager = ContentManager(
                user_id=user_id,
                type=permission_type,
                file_id=file_id
            )
        
        else:
            # Missing required IDs for the selected type
            missing_field = 'channel_id' if permission_type == 'channel' else ('folder_id' if permission_type == 'folder' else 'file_id')
            return jsonify({'error': f'Required field missing: {missing_field}'}), 400
        
        # Save to database
        db.session.add(manager)
        db.session.commit()
        
        return jsonify(manager.to_dict())
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding content manager: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/content_manager/<int:manager_id>', methods=['DELETE'])
def delete_content_manager(manager_id):
    """
    Delete a content manager entry
    
    Path parameter:
    - manager_id: ID of the content manager entry to delete
    """
    try:
        manager = ContentManager.query.get(manager_id)
        
        if not manager:
            return jsonify({'error': f'Content manager entry with ID {manager_id} not found'}), 404
        
        db.session.delete(manager)
        db.session.commit()
        
        return jsonify({'message': 'Content manager entry deleted successfully'})
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting content manager: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/content_manager/<int:manager_id>', methods=['PUT'])
def update_content_manager(manager_id):
    """
    Update an existing content manager entry
    
    Path parameter:
    - manager_id: ID of the content manager entry to update
    
    Request body:
    - user_id: ID of the user to add as manager
    - type: Type of permission ('channel', 'folder', or 'file')
    - file_id: ID of the file (when type is 'file')
    - folder_id: ID of the folder (when type is 'folder')
    - channel_id: ID of the channel (when type is 'channel')
    """
    try:
        # Find the manager entry
        manager = ContentManager.query.get(manager_id)
        
        if not manager:
            return jsonify({'error': f'Content manager entry with ID {manager_id} not found'}), 404
        
        data = request.json
        
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        # Store original user_id for duplicate checking
        original_user_id = manager.user_id
        original_type = manager.type
        original_channel_id = manager.channel_id
        original_folder_id = manager.folder_id
        original_file_id = manager.file_id
        
        # Update user_id if provided
        if 'user_id' in data:
            user_id = data['user_id']
            # Validate user exists with case-insensitive search
            user = Users.query.filter(Users.id.ilike(user_id)).first()
            if not user:
                return jsonify({'error': f'User with ID {user_id} not found'}), 404
            # Use the actual user ID from the database to ensure consistent casing
            user_id = user.id
            manager.user_id = user_id
        else:
            user_id = original_user_id
        
        # Update type and related IDs if provided
        if 'type' in data:
            permission_type = data['type']
            manager.type = permission_type
            
            # Reset all IDs
            manager.file_id = None
            manager.folder_id = None
            manager.channel_id = None
            
            # Set appropriate ID based on type
            if permission_type == 'channel' and 'channel_id' in data:
                channel_id = int(data['channel_id'])
                
                # Verify channel exists
                channel = ContentRelChannels.query.filter_by(id=channel_id, is_deleted=False).first()
                if not channel:
                    return jsonify({'error': f'Channel with ID {channel_id} not found'}), 404
                
                # Check for duplicates, but ignore if it's the same record being updated
                duplicate = ContentManager.query.filter_by(
                    user_id=user_id,
                    type='channel',
                    channel_id=channel_id
                ).filter(ContentManager.id != manager_id).first()
                
                if duplicate:
                    return jsonify({'error': f'User {user_id} already has channel manager permission for this channel'}), 409
                
                manager.channel_id = channel_id
            
            elif permission_type == 'folder' and 'folder_id' in data:
                folder_id = int(data['folder_id'])
                
                # Verify folder exists
                folder = ContentRelFolders.query.filter_by(id=folder_id, is_deleted=False).first()
                if not folder:
                    return jsonify({'error': f'Folder with ID {folder_id} not found'}), 404
                
                # Check for duplicates, but ignore if it's the same record being updated
                duplicate = ContentManager.query.filter_by(
                    user_id=user_id,
                    type='folder',
                    folder_id=folder_id
                ).filter(ContentManager.id != manager_id).first()
                
                if duplicate:
                    return jsonify({'error': f'User {user_id} already has folder manager permission for this folder'}), 409
                
                manager.folder_id = folder_id
            
            elif permission_type == 'file' and 'file_id' in data:
                file_id = int(data['file_id'])
                
                # Verify file exists
                file = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
                if not file:
                    return jsonify({'error': f'File with ID {file_id} not found'}), 404
                
                # Check for duplicates, but ignore if it's the same record being updated
                duplicate = ContentManager.query.filter_by(
                    user_id=user_id,
                    type='file',
                    file_id=file_id
                ).filter(ContentManager.id != manager_id).first()
                
                if duplicate:
                    return jsonify({'error': f'User {user_id} already has file manager permission for this file'}), 409
                
                manager.file_id = file_id
            
            else:
                # Missing required IDs for the selected type
                missing_field = 'channel_id' if permission_type == 'channel' else ('folder_id' if permission_type == 'folder' else 'file_id')
                return jsonify({'error': f'Required field missing: {missing_field}'}), 400
        else:
            # Type not being updated, but check for duplicate if user_id is updated
            if 'user_id' in data:
                # Current settings
                if manager.type == 'channel' and manager.channel_id:
                    duplicate = ContentManager.query.filter_by(
                        user_id=user_id,
                        type='channel',
                        channel_id=manager.channel_id
                    ).filter(ContentManager.id != manager_id).first()
                    
                    if duplicate:
                        return jsonify({'error': f'User {user_id} already has channel manager permission for this channel'}), 409
                
                elif manager.type == 'folder' and manager.folder_id:
                    duplicate = ContentManager.query.filter_by(
                        user_id=user_id,
                        type='folder',
                        folder_id=manager.folder_id
                    ).filter(ContentManager.id != manager_id).first()
                    
                    if duplicate:
                        return jsonify({'error': f'User {user_id} already has folder manager permission for this folder'}), 409
                
                elif manager.type == 'file' and manager.file_id:
                    duplicate = ContentManager.query.filter_by(
                        user_id=user_id,
                        type='file',
                        file_id=manager.file_id
                    ).filter(ContentManager.id != manager_id).first()
                    
                    if duplicate:
                        return jsonify({'error': f'User {user_id} already has file manager permission for this file'}), 409
        
        # Save to database
        db.session.commit()
        
        return jsonify(manager.to_dict())
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating content manager: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ======== R2 STORAGE HELPER FUNCTIONS ========

def get_r2_client():
    """
    Create and return a configured R2 (S3-compatible) client
    """
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
        logger.error(f"Failed to create R2 client: {str(e)}")
        raise

def generate_r2_signed_url(object_key, expires_in=3600, method='GET'):
    """
    Generate a pre-signed URL for R2 object
    
    Args:
        object_key: The R2 object key (file path)
        expires_in: URL expiration time in seconds (default: 1 hour)
        method: HTTP method ('GET' for download, 'PUT' for upload)
        
    Returns:
        Pre-signed URL string
    """
    try:
        r2_client = get_r2_client()
        bucket_name = current_app.config.get('R2_BUCKET_NAME')
        
        if not bucket_name:
            raise ValueError("R2 bucket name not found in configuration")
        
        if method == 'GET':
            # Generate signed URL for download
            signed_url = r2_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': object_key},
                ExpiresIn=expires_in
            )
        elif method == 'PUT':
            # Generate signed URL for upload
            signed_url = r2_client.generate_presigned_url(
                'put_object',
                Params={'Bucket': bucket_name, 'Key': object_key},
                ExpiresIn=expires_in
            )
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        return signed_url
    except Exception as e:
        logger.error(f"Failed to generate R2 signed URL: {str(e)}")
        raise

def check_r2_object_exists(object_key):
    """
    Check if an object exists in R2
    
    Args:
        object_key: The R2 object key to check
        
    Returns:
        Boolean indicating if object exists
    """
    try:
        r2_client = get_r2_client()
        bucket_name = current_app.config.get('R2_BUCKET_NAME')
        
        r2_client.head_object(Bucket=bucket_name, Key=object_key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        else:
            logger.error(f"Error checking R2 object existence: {str(e)}")
            raise
    except Exception as e:
        logger.error(f"Failed to check R2 object existence: {str(e)}")
        raise

def delete_r2_object(object_key):
    """
    Delete an object from R2
    
    Args:
        object_key: The R2 object key to delete
        
    Returns:
        Boolean indicating success
    """
    try:
        r2_client = get_r2_client()
        bucket_name = current_app.config.get('R2_BUCKET_NAME')
        
        r2_client.delete_object(Bucket=bucket_name, Key=object_key)
        return True
    except Exception as e:
        logger.error(f"Failed to delete R2 object: {str(e)}")
        return False

def generate_r2_object_key(file_id, filename, is_page_detail=False, page_detail_name=None):
    """
    Generate an object key for R2 storage based on content hierarchy
    
    Args:
        file_id: The file ID from database (page ID for regular files, page_detail ID for details)
        filename: Original filename
        is_page_detail: Whether this is a page detail file
        page_detail_name: Name of the page detail (if applicable)
        
    Returns:
        Object key string following the pattern:
        - For pages: channel/folder1/folder2/file.ext
        - For page details: channel/folder1/folder2/file/detail.ext
    """
    try:
        # Build the detailed path using existing logic
        if is_page_detail:
            # For page details, get the path components
            detail = ContentRelPageDetails.query.filter_by(id=file_id, is_deleted=False).first()
            if not detail:
                raise ValueError(f"Page detail with ID {file_id} not found")
            
            # Get parent page
            parent_page = ContentRelPages.query.filter_by(id=detail.page_id, is_deleted=False).first()
            if not parent_page:
                raise ValueError(f"Parent page for detail {file_id} not found")
            
            # Build path components starting from page
            path_components = []
            folder_id = parent_page.folder_id
            
            # Traverse folder hierarchy
            while folder_id is not None:
                folder = ContentRelFolders.query.filter_by(id=folder_id, is_deleted=False).first()
                if not folder:
                    break
                
                path_components.append(folder.name)
                
                if folder.parent_id is None:
                    # Top-level folder, get the channel
                    channel = ContentRelChannels.query.filter_by(id=folder.channel_id, is_deleted=False).first()
                    if channel:
                        path_components.append(channel.name)
                    break
                
                folder_id = folder.parent_id
            
            # Reverse to get channel -> folder order
            path_components.reverse()
            
            # Add page name WITHOUT extension for page details folder
            page_name_without_ext = os.path.splitext(parent_page.name)[0] if parent_page.name else "page"
            path_components.append(page_name_without_ext)
            
            # Add detail name with proper extension
            detail_name = page_detail_name or detail.name or "detail"
            
            # Extract file extension and apply to detail name
            _, ext = os.path.splitext(filename)
            if not detail_name.endswith(ext):
                detail_name += ext
                
            path_components.append(detail_name)
            
        else:
            # For regular pages
            page = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
            if not page:
                raise ValueError(f"Page with ID {file_id} not found")
            
            # Build path components
            path_components = []
            folder_id = page.folder_id
            
            # Traverse folder hierarchy
            while folder_id is not None:
                folder = ContentRelFolders.query.filter_by(id=folder_id, is_deleted=False).first()
                if not folder:
                    break
                
                path_components.append(folder.name)
                
                if folder.parent_id is None:
                    # Top-level folder, get the channel
                    channel = ContentRelChannels.query.filter_by(id=folder.channel_id, is_deleted=False).first()
                    if channel:
                        path_components.append(channel.name)
                    break
                
                folder_id = folder.parent_id
            
            # Reverse to get channel -> folder order
            path_components.reverse()
            
            # Add page name with proper extension
            page_name = page.name or "file"
            _, ext = os.path.splitext(filename)
            if not page_name.endswith(ext):
                page_name += ext
                
            path_components.append(page_name)
        
        # Join components with forward slash for R2 object key
        object_key = '/'.join(path_components)
        
        # Replace any characters that are problematic for object keys
        # Keep more Unicode characters but replace truly problematic ones
        # Replace multiple consecutive spaces/underscores with single underscore
        object_key = re.sub(r'\s+', ' ', object_key)  # Normalize spaces first
        
        # Replace characters that are definitely problematic for S3/R2 object keys
        # But preserve Unicode characters like Korean text and fraction slash
        problematic_chars = r'[<>:"|?*\x00-\x1f\x7f]'  # Control chars and filesystem reserved chars
        object_key = re.sub(problematic_chars, '_', object_key)
        
        # Replace backslashes with forward slashes (Windows path separators)
        object_key = object_key.replace('\\', '/')
        
        # Clean up multiple consecutive slashes
        object_key = re.sub(r'/+', '/', object_key)
        
        return object_key
        
    except Exception as e:
        logger.error(f"Error generating R2 object key: {str(e)}")
        # Fallback to simple structure if path building fails
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        _, ext = os.path.splitext(filename)
        fallback_key = f"fallback/{file_id}/{timestamp}_{unique_id}{ext}"
        return fallback_key

# ======== R2 API ENDPOINTS ========

@api_contents_bp.route('/file/<int:file_id>/r2-upload-url', methods=['POST'])
@jwt_required(locations=['headers','cookies'])
def get_r2_upload_url(file_id):
    """
    Generate a pre-signed URL for direct upload to R2
    
    Path parameter:
    - file_id: ID of the file
    
    Request body:
    - filename: Name of the image file
    - content_type: MIME type of the image (e.g., image/jpeg)
    - file_size: Size of the file in bytes
    - is_modify: (Optional) Boolean flag indicating if this is a modification of existing image
    """
    try:
        # Check user permissions
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user or user.role_id not in [1, 2, 999]:  # Admin, reviewer, or developer only
            return jsonify({'error': 'Permission denied. Admin or reviewer role required.'}), 403
        
        # Get the file
        page = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
        if not page:
            return jsonify({'error': 'File not found'}), 404
        
        # Get request data
        request_data = request.json
        if not request_data:
            return jsonify({'error': 'Request body is required'}), 400
        
        filename = request_data.get('filename', '')
        content_type = request_data.get('content_type', '')
        file_size = request_data.get('file_size', 0)
        is_modify = request_data.get('is_modify', False)
        
        if not filename:
            return jsonify({'error': 'Filename is required'}), 400
        
        # Check if file already has an image (only for new uploads, not modifications)
        if not is_modify and page.object_id and page.object_id.strip() != '':
            return jsonify({'error': 'File already has an image. Use modify endpoint to change it.'}), 409
        
        # For modifications, check if file has an image to modify
        if is_modify and (not page.object_id or page.object_id.strip() == ''):
            return jsonify({'error': 'No image associated with this file. Use upload endpoint instead.'}), 404
        
        # Validate file type
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf', '.webm', '.mp4', '.avi', '.mov', '.wmv', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx'}
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in allowed_extensions:
            return jsonify({'error': f'Invalid file type {file_ext}. Allowed types: {", ".join(allowed_extensions)}'}), 400
        
        # Validate file size (100MB limit)
        if file_size > 100 * 1024 * 1024:  # 100MB
            return jsonify({'error': 'File size too large. Maximum 100MB allowed.'}), 400
        
        # Generate object key based on content hierarchy
        object_key = generate_r2_object_key(file_id, filename, is_page_detail=False)
        
        # Generate pre-signed URL for upload
        upload_url = generate_r2_signed_url(object_key, expires_in=1800, method='PUT')  # 30 minutes
        
        return jsonify({
            'upload_url': upload_url,
            'object_key': object_key,
            'file_id': file_id,
            'is_modify': is_modify,
            'old_object_id': page.object_id if is_modify else None,
            'expires_in': 1800,
            'message': 'R2 upload URL generated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error generating R2 upload URL: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/file/<int:file_id>/confirm-r2-upload', methods=['POST'])
@jwt_required(locations=['headers','cookies'])
def confirm_r2_upload(file_id):
    """
    Confirm that a direct upload to R2 was successful and update the database
    
    Path parameter:
    - file_id: ID of the file
    
    Request body:
    - object_key: The R2 object key where the file was uploaded
    - filename: Name of the uploaded file
    """
    try:
        # Check user permissions
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user or user.role_id not in [1, 2, 999]:  # Admin, reviewer, or developer only
            return jsonify({'error': 'Permission denied. Admin or reviewer role required.'}), 403
        
        # Get the file
        page = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
        if not page:
            return jsonify({'error': 'File not found'}), 404
        
        # Get request data
        request_data = request.json
        if not request_data:
            return jsonify({'error': 'Request body is required'}), 400
        
        object_key = request_data.get('object_key', '')
        filename = request_data.get('filename', '')
        
        if not object_key:
            return jsonify({'error': 'object_key is required'}), 400
        
        # Verify the object exists in R2
        if not check_r2_object_exists(object_key):
            return jsonify({'error': 'Object not found in R2 storage'}), 404
        
        # Update the page with the new object_id (storing the R2 object key)
        page.object_id = object_key
        page.updated_at = datetime.datetime.now()
        db.session.commit()
        
        return jsonify({
            'message': 'R2 upload confirmed and database updated successfully',
            'object_key': object_key,
            'file_id': file_id,
            'filename': filename
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error confirming R2 upload: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/file/<int:file_id>/modify-r2-image', methods=['PUT'])
@jwt_required(locations=['headers','cookies'])
def modify_r2_image(file_id):
    """
    Update the R2 object key for an existing file (after successful upload)
    
    Path parameter:
    - file_id: ID of the file
    
    Request body:
    - object_key: The new R2 object key
    - filename: Name of the uploaded file
    """
    try:
        # Check user permissions
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user or user.role_id not in [1, 2, 999]:  # Admin, reviewer, or developer only
            return jsonify({'error': 'Permission denied. Admin or reviewer role required.'}), 403
        
        # Get the file
        page = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
        if not page:
            return jsonify({'error': 'File not found'}), 404
        
        # Check if file has an image to modify
        if not page.object_id or page.object_id.strip() == '':
            return jsonify({'error': 'No image associated with this file. Use upload endpoint instead.'}), 404
        
        # Get request data
        request_data = request.json
        if not request_data:
            return jsonify({'error': 'Request body is required'}), 400
        
        new_object_key = request_data.get('object_key', '')
        filename = request_data.get('filename', '')
        
        if not new_object_key:
            return jsonify({'error': 'object_key is required'}), 400
        
        # Verify the new object exists in R2
        if not check_r2_object_exists(new_object_key):
            return jsonify({'error': 'New object not found in R2 storage'}), 404
        
        old_object_key = page.object_id
        
        # Update the page with the new object_key
        page.object_id = new_object_key
        page.updated_at = datetime.datetime.now()
        db.session.commit()
        
        # Delete old object from R2 (best effort)
        if old_object_key and old_object_key != new_object_key:
            delete_success = delete_r2_object(old_object_key)
            if not delete_success:
                logger.warning(f"Failed to delete old R2 object: {old_object_key}")
        
        return jsonify({
            'message': 'R2 image modified successfully',
            'old_object_key': old_object_key,
            'new_object_key': new_object_key,
            'file_id': file_id,
            'filename': filename
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error modifying R2 image: {str(e)}")
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
        # Check R2 configuration first
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
        
        # Check if user has access to this file
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get the file
        page = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
        if not page:
            return jsonify({'error': 'File not found'}), 404
        
        # Check if R2 file exists (using the new approach)
        # First try to find the R2 object using standard extensions
        page_name = page.name or f"file_{file_id}"
        image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf']
        
        r2_object_key = None
        
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
            service = ContentHierarchyService()
            folder_ids, file_ids = service.get_user_accessible_content(int(user_id))
            
            if file_id not in file_ids:
                return jsonify({'error': 'Access denied'}), 403
        
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
        logger.error(f"Error generating R2 image URL: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/page-detail/<int:detail_id>/upload-content', methods=['POST'])
@jwt_required(locations=['headers','cookies'])
def upload_page_detail_content(detail_id):
    """
    Upload content file for a page detail (traditional upload to R2)
    
    Path parameter:
    - detail_id: ID of the page detail
    
    Form data:
    - file: The content file to upload
    """
    try:
        # Check user permissions
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user or user.role_id not in [1, 2, 999]:  # Admin, reviewer, or developer only
            return jsonify({'error': 'Permission denied. Admin or reviewer role required.'}), 403
        
        # Get the page detail
        detail = ContentRelPageDetails.query.filter_by(id=detail_id, is_deleted=False).first()
        if not detail:
            return jsonify({'error': 'Page detail not found'}), 404
        
        # Check if file is provided
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Validate file type
        allowed_extensions = {'.pdf', '.webm', '.mp4', '.avi', '.mov', '.wmv', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return jsonify({'error': f'Invalid file type {file_ext}. Allowed types: {", ".join(allowed_extensions)}'}), 400
        
        # Validate file size (100MB limit)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > 100 * 1024 * 1024:  # 100MB
            return jsonify({'error': 'File size too large. Maximum 100MB allowed.'}), 400
        
        # Generate object key based on content hierarchy for page detail
        object_key = generate_r2_object_key(detail_id, file.filename, is_page_detail=True)
        
        # Upload directly to R2
        try:
            r2_client = get_r2_client()
            bucket_name = current_app.config.get('R2_BUCKET_NAME')
            
            # Upload file to R2
            r2_client.upload_fileobj(
                file,
                bucket_name,
                object_key,
                ExtraArgs={'ContentType': file.content_type or 'application/octet-stream'}
            )
            
            # Update the page detail with the object key
            detail.object_id = object_key
            # has_content is now computed from object_id, so no need to set it explicitly
            detail.updated_at = datetime.datetime.now()
            db.session.commit()
            
            return jsonify({
                'message': 'File uploaded successfully to page detail',
                'object_key': object_key,
                'detail_id': detail_id,
                'filename': file.filename
            })
            
        except Exception as upload_error:
            logger.error(f"R2 upload failed: {str(upload_error)}")
            return jsonify({'error': f'Upload failed: {str(upload_error)}'}), 500
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error uploading page detail content: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/page-detail/<int:detail_id>/download', methods=['GET'])
@jwt_required(locations=['headers','cookies'])
def download_page_detail(detail_id):
    """
    Generate a signed URL for downloading page detail content from R2
    
    Path parameter:
    - detail_id: ID of the page detail
    """
    try:
        # Check user permissions
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get the page detail
        detail = ContentRelPageDetails.query.filter_by(id=detail_id, is_deleted=False).first()
        if not detail:
            return jsonify({'error': 'Page detail not found'}), 404
        
        # Check if detail has content (using the computed property)
        if not detail.object_id or detail.object_id.strip() == '' or not detail.has_content:
            return jsonify({'error': 'No content associated with this page detail'}), 404
        
        # Check user permissions (admin, developer, or has specific access)
        if user.role_id not in [1, 2, 999]:  # Not admin, reviewer, or developer
            # Check if user has specific access to the parent page
            parent_page = ContentRelPages.query.filter_by(id=detail.page_id, is_deleted=False).first()
            if parent_page:
                service = ContentHierarchyService()
                folder_ids, file_ids = service.get_user_accessible_content(int(user_id))
                
                if parent_page.id not in file_ids:
                    return jsonify({'error': 'Access denied'}), 403
            else:
                return jsonify({'error': 'Parent page not found'}), 404
        
        # Generate pre-signed URL for download
        try:
            signed_url = generate_r2_signed_url(detail.object_id, expires_in=3600, method='GET')
            
            # For direct download, redirect to the signed URL
            from flask import redirect
            return redirect(signed_url)
            
        except Exception as e:
            logger.error(f"Failed to generate download URL: {str(e)}")
            return jsonify({'error': 'Failed to generate download URL'}), 500
        
    except Exception as e:
        logger.error(f"Error downloading page detail: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/file/<int:file_id>/r2-object-key', methods=['GET'])
@jwt_required(locations=['headers','cookies'])
def get_r2_object_key_preview(file_id):
    """
    Get the R2 object key that would be used for a file (for debugging/preview)
    
    Path parameter:
    - file_id: ID of the file (page or page detail)
    
    Query parameters:
    - filename: Filename to use for key generation
    - is_page_detail: Whether this is a page detail (default: false)
    """
    try:
        # Check user permissions (basic check)
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get query parameters
        filename = request.args.get('filename', 'example.pdf')
        is_page_detail = request.args.get('is_page_detail', 'false').lower() == 'true'
        
        # Generate the object key
        object_key = generate_r2_object_key(file_id, filename, is_page_detail=is_page_detail)
        
        return jsonify({
            'file_id': file_id,
            'filename': filename,
            'is_page_detail': is_page_detail,
            'object_key': object_key,
            'message': 'This is the R2 object key that would be used for this file'
        })
        
    except Exception as e:
        logger.error(f"Error getting R2 object key preview: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ======== LEGACY CLOUDFLARE IMAGES (DEPRECATED) ========

# Image handling endpoints

def generate_signed_url(image_id, variant='public', expire_in_seconds=3600):
    """
    Generate a signed URL for Cloudflare Images
    
    Args:
        image_id: The Cloudflare image ID
        variant: Image variant (default: 'public')
        expire_in_seconds: URL expiration time in seconds
        
    Returns:
        Signed URL string
    """
    account_hash = current_app.config.get('CLOUDFLARE_ACCOUNT_HASH')
    signing_key = current_app.config.get('CLOUDFLARE_SIGNING_KEY')
    
    if not account_hash or not signing_key:
        raise ValueError("Cloudflare configuration not found")
    
    expires = int(time.time()) + expire_in_seconds
    query = f"expires={expires}"
    
    # Create HMAC signature
    hmac_obj = hmac.new(
        signing_key.encode('utf-8'),
        query.encode('utf-8'),
        hashlib.sha256
    )
    signature = hmac_obj.hexdigest()
    
    base_url = f"https://imagedelivery.net/{account_hash}/{image_id}/{variant}"
    return f"{base_url}?{query}&sig={signature}"

@api_contents_bp.route('/file/<int:file_id>/image-url', methods=['GET'])
@jwt_required(locations=['headers','cookies'])
def get_file_image_url(file_id):
    """
    Get a signed URL for viewing a file's image
    
    Path parameter:
    - file_id: ID of the file
    
    Query parameters:
    - variant: Image variant (optional, default: 'public')
    - expires: Expiration time in seconds (optional, default: 3600)
    """
    try:
        # Check if user has access to this file
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get the file
        page = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
        if not page:
            return jsonify({'error': 'File not found'}), 404
        
        # Check if file has an image (object_id is not null/empty)
        if not page.object_id or page.object_id.strip() == '':
            return jsonify({'error': 'No image associated with this file'}), 404
        
        # Check user permissions (admin, developer, or has specific access)
        if user.role_id not in [1, 2, 999]:  # Not admin, reviewer, or developer
            # Check if user has specific access to this file
            service = ContentHierarchyService()
            folder_ids, file_ids = service.get_user_accessible_content(int(user_id))
            
            if file_id not in file_ids:
                return jsonify({'error': 'Access denied'}), 403
        
        # Get query parameters
        variant = request.args.get('variant', 'public')
        expires = int(request.args.get('expires', 3600))
        
        # Generate signed URL
        signed_url = generate_signed_url(page.object_id, variant, expires)
        
        return jsonify({
            'signed_url': signed_url,
            'expires_in': expires,
            'image_id': page.object_id
        })
        
    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        return jsonify({'error': 'Server configuration error'}), 500
    except Exception as e:
        logger.error(f"Error generating image URL: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/file/<int:file_id>/upload-image', methods=['POST'])
@jwt_required(locations=['headers','cookies'])
def upload_file_image(file_id):
    """
    Upload an image for a file to Cloudflare Images
    
    Path parameter:
    - file_id: ID of the file
    
    Form data:
    - image: The image file to upload
    """
    try:
        # Check user permissions
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user or user.role_id not in [1, 2, 999]:  # Admin, reviewer, or developer only
            return jsonify({'error': 'Permission denied. Admin or reviewer role required.'}), 403
        
        # Get the file
        page = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
        if not page:
            return jsonify({'error': 'File not found'}), 404
        
        # Check if file already has an image
        if page.object_id and page.object_id.strip() != '':
            return jsonify({'error': 'File already has an image. Use modify endpoint to change it.'}), 409
        
        # Check if image file is provided
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        
        image_file = request.files['image']
        if image_file.filename == '':
            return jsonify({'error': 'No image file selected'}), 400
        
        # Validate file type
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
        file_ext = os.path.splitext(image_file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return jsonify({'error': 'Invalid file type. Only PNG, JPG, JPEG, GIF, and WebP are allowed.'}), 400
        
        # Validate file size (10MB limit)
        image_file.seek(0, os.SEEK_END)
        file_size = image_file.tell()
        image_file.seek(0)
        
        if file_size > 10 * 1024 * 1024:  # 10MB
            return jsonify({'error': 'File size too large. Maximum 10MB allowed.'}), 400
        
        # Upload to Cloudflare Images
        account_id = current_app.config.get('CLOUDFLARE_ACCOUNT_ID')
        api_token = current_app.config.get('CLOUDFLARE_API_TOKEN')
        
        if not account_id or not api_token:
            return jsonify({'error': 'Cloudflare configuration not found'}), 500
        
        # Prepare the upload
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/images/v1"
        headers = {
            'Authorization': f'Bearer {api_token}'
        }
        
        # Prepare file data
        files = {
            'file': (image_file.filename, image_file.stream, image_file.content_type)
        }
        
        # Optional metadata
        data = {
            'metadata': json.dumps({
                'file_id': str(file_id),
                'filename': image_file.filename,
                'uploaded_by': str(user_id),
                'upload_time': datetime.datetime.now().isoformat()
            })
        }
        
        # Upload to Cloudflare
        response = requests.post(url, headers=headers, files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                cloudflare_id = result['result']['id']
                
                # Update the page with the new object_id
                page.object_id = cloudflare_id
                page.updated_at = datetime.datetime.now()
                db.session.commit()
                
                return jsonify({
                    'message': 'Image uploaded successfully',
                    'object_id': cloudflare_id,
                    'file_id': file_id,
                    'cloudflare_response': result['result']
                })
            else:
                return jsonify({'error': 'Cloudflare upload failed', 'details': result}), 500
        else:
            return jsonify({'error': f'Cloudflare API error: {response.status_code}', 'details': response.text}), 500
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error uploading image: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/file/<int:file_id>/remove-image', methods=['DELETE'])
@jwt_required(locations=['headers','cookies'])
def remove_file_image(file_id):
    """
    Remove the image associated with a file
    
    Path parameter:
    - file_id: ID of the file
    """
    try:
        # Check user permissions
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user or user.role_id not in [1, 2, 999]:  # Admin, reviewer, or developer only
            return jsonify({'error': 'Permission denied. Admin or reviewer role required.'}), 403
        
        # Get the file
        page = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
        if not page:
            return jsonify({'error': 'File not found'}), 404
        
        # Check if file has an image
        if not page.object_id or page.object_id.strip() == '':
            return jsonify({'error': 'No image associated with this file'}), 404
        
        # Delete from Cloudflare Images
        account_id = current_app.config.get('CLOUDFLARE_ACCOUNT_ID')
        api_token = current_app.config.get('CLOUDFLARE_API_TOKEN')
        
        if account_id and api_token:
            url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/images/v1/{page.object_id}"
            headers = {
                'Authorization': f'Bearer {api_token}'
            }
            
            # Delete from Cloudflare
            response = requests.delete(url, headers=headers)
            
            if response.status_code != 200:
                logger.warning(f"Failed to delete image from Cloudflare: {response.status_code} - {response.text}")
                # Continue anyway to clean up database
        
        # Clear the object_id from database
        page.object_id = None
        page.updated_at = datetime.datetime.now()
        db.session.commit()
        
        return jsonify({
            'message': 'Image removed successfully',
            'file_id': file_id
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error removing image: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/file/<int:file_id>/modify-image', methods=['PUT'])
@jwt_required(locations=['headers','cookies'])
def modify_file_image(file_id):
    """
    Modify/replace the image associated with a file
    
    This endpoint now supports both direct file upload and direct Cloudflare ID update for optimized flow
    
    Path parameter:
    - file_id: ID of the file
    
    Form data (traditional upload):
    - image: The new image file to upload
    
    JSON data (optimized direct upload):
    - cloudflare_id: The new image ID from Cloudflare after direct upload
    - filename: Name of the uploaded file
    """
    try:
        # Check user permissions
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user or user.role_id not in [1, 2, 999]:  # Admin, reviewer, or developer only
            return jsonify({'error': 'Permission denied. Admin or reviewer role required.'}), 403
        
        # Get the file
        page = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
        if not page:
            return jsonify({'error': 'File not found'}), 404
        
        # Check if file has an image to modify
        if not page.object_id or page.object_id.strip() == '':
            return jsonify({'error': 'No image associated with this file. Use upload endpoint instead.'}), 404
        
        # Check if this is a direct upload (JSON) or traditional upload (form data)
        if request.is_json:
            # Direct upload flow - Cloudflare ID is provided
            request_data = request.json
            if not request_data:
                return jsonify({'error': 'Request body is required'}), 400
            
            cloudflare_id = request_data.get('cloudflare_id', '')
            filename = request_data.get('filename', '')
            
            if not cloudflare_id:
                return jsonify({'error': 'cloudflare_id is required for direct upload'}), 400
            
            # Get Cloudflare configuration for verification
            account_id = current_app.config.get('CLOUDFLARE_ACCOUNT_ID')
            api_token = current_app.config.get('CLOUDFLARE_API_TOKEN')
            
            if not account_id or not api_token:
                return jsonify({'error': 'Cloudflare configuration not found'}), 500
            
            # Verify the new image exists in Cloudflare
            verify_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/images/v1/{cloudflare_id}"
            headers = {
                'Authorization': f'Bearer {api_token}'
            }
            
            verify_response = requests.get(verify_url, headers=headers)
            
            if verify_response.status_code != 200:
                return jsonify({'error': 'Failed to verify new image in Cloudflare'}), 400
            
            verify_result = verify_response.json()
            if not verify_result.get('success'):
                return jsonify({'error': 'New image verification failed', 'details': verify_result}), 400
            
            old_object_id = page.object_id
            
            # Update the page with the new object_id
            page.object_id = cloudflare_id
            page.updated_at = datetime.datetime.now()
            db.session.commit()
            
            # Delete old image from Cloudflare (best effort)
            if old_object_id:
                delete_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/images/v1/{old_object_id}"
                delete_response = requests.delete(delete_url, headers=headers)
                
                if delete_response.status_code != 200:
                    logger.warning(f"Failed to delete old image from Cloudflare: {delete_response.status_code} - {delete_response.text}")
                    # Continue anyway since new image is uploaded and DB is updated
            
            return jsonify({
                'message': 'Image modified successfully (direct upload)',
                'old_object_id': old_object_id,
                'new_object_id': cloudflare_id,
                'file_id': file_id,
                'filename': filename
            })
        
        else:
            # Traditional upload flow - file is provided
            # Check if new image file is provided
            if 'image' not in request.files:
                return jsonify({'error': 'No image file provided'}), 400
            
            image_file = request.files['image']
            if image_file.filename == '':
                return jsonify({'error': 'No image file selected'}), 400
            
            # Validate file type
            allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
            file_ext = os.path.splitext(image_file.filename)[1].lower()
            if file_ext not in allowed_extensions:
                return jsonify({'error': 'Invalid file type. Only PNG, JPG, JPEG, GIF, and WebP are allowed.'}), 400
            
            # Validate file size (10MB limit)
            image_file.seek(0, os.SEEK_END)
            file_size = image_file.tell()
            image_file.seek(0)
            
            if file_size > 10 * 1024 * 1024:  # 10MB
                return jsonify({'error': 'File size too large. Maximum 10MB allowed.'}), 400
            
            # Get Cloudflare configuration
            account_id = current_app.config.get('CLOUDFLARE_ACCOUNT_ID')
            api_token = current_app.config.get('CLOUDFLARE_API_TOKEN')
            
            if not account_id or not api_token:
                return jsonify({'error': 'Cloudflare configuration not found'}), 500
            
            old_object_id = page.object_id
            
            # Upload new image to Cloudflare Images
            url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/images/v1"
            headers = {
                'Authorization': f'Bearer {api_token}'
            }
            
            # Prepare file data
            files = {
                'file': (image_file.filename, image_file.stream, image_file.content_type)
            }
            
            # Optional metadata
            data = {
                'metadata': json.dumps({
                    'file_id': str(file_id),
                    'filename': image_file.filename,
                    'modified_by': str(user_id),
                    'modify_time': datetime.datetime.now().isoformat(),
                    'replaced_image_id': old_object_id
                })
            }
            
            # Upload new image to Cloudflare
            response = requests.post(url, headers=headers, files=files, data=data)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    new_cloudflare_id = result['result']['id']
                    
                    # Update the page with the new object_id
                    page.object_id = new_cloudflare_id
                    page.updated_at = datetime.datetime.now()
                    db.session.commit()
                    
                    # Delete old image from Cloudflare (best effort)
                    if old_object_id:
                        delete_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/images/v1/{old_object_id}"
                        delete_response = requests.delete(delete_url, headers=headers)
                        
                        if delete_response.status_code != 200:
                            logger.warning(f"Failed to delete old image from Cloudflare: {delete_response.status_code} - {delete_response.text}")
                            # Continue anyway since new image is uploaded and DB is updated
                    
                    return jsonify({
                        'message': 'Image modified successfully (traditional upload)',
                        'old_object_id': old_object_id,
                        'new_object_id': new_cloudflare_id,
                        'file_id': file_id,
                        'cloudflare_response': result['result']
                    })
                else:
                    return jsonify({'error': 'Cloudflare upload failed', 'details': result}), 500
            else:
                return jsonify({'error': f'Cloudflare API error: {response.status_code}', 'details': response.text}), 500
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error modifying image: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ====== OPTIMIZED DIRECT UPLOAD ENDPOINTS (Add to contents_routes.py) ======

# Direct Upload Endpoints (Optimized for Performance)

@api_contents_bp.route('/file/<int:file_id>/direct-upload-url', methods=['POST'])
@jwt_required(locations=['headers','cookies'])
def get_direct_upload_url(file_id):
    """
    Get a direct upload URL for Cloudflare Images (optimized flow)
    
    This endpoint generates a signed URL that allows the client to upload directly to Cloudflare,
    bypassing the backend server to reduce load and improve performance.
    
    Path parameter:
    - file_id: ID of the file
    
    Request body:
    - filename: Name of the image file
    - content_type: MIME type of the image (e.g., image/jpeg)
    - file_size: Size of the file in bytes
    - is_modify: (Optional) Boolean flag indicating if this is a modification of existing image
    """
    try:
        # Check user permissions
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user or user.role_id not in [1, 2, 999]:  # Admin, reviewer, or developer only
            return jsonify({'error': 'Permission denied. Admin or reviewer role required.'}), 403
        
        # Get the file
        page = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
        if not page:
            return jsonify({'error': 'File not found'}), 404
        
        # Get request data
        request_data = request.json
        if not request_data:
            return jsonify({'error': 'Request body is required'}), 400
        
        filename = request_data.get('filename', '')
        content_type = request_data.get('content_type', '')
        file_size = request_data.get('file_size', 0)
        is_modify = request_data.get('is_modify', False)
        
        if not filename:
            return jsonify({'error': 'Filename is required'}), 400
        
        # Check if file already has an image (only for new uploads, not modifications)
        if not is_modify and page.object_id and page.object_id.strip() != '':
            return jsonify({'error': 'File already has an image. Use modify endpoint to change it.'}), 409
        
        # For modifications, check if file has an image to modify
        if is_modify and (not page.object_id or page.object_id.strip() == ''):
            return jsonify({'error': 'No image associated with this file. Use upload endpoint instead.'}), 404
        
        # Validate file type
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in allowed_extensions:
            return jsonify({'error': 'Invalid file type. Only PNG, JPG, JPEG, GIF, and WebP are allowed.'}), 400
        
        # Validate file size (100MB limit)
        if file_size > 100 * 1024 * 1024:  # 10MB
            return jsonify({'error': 'File size too large. Maximum 10MB allowed.'}), 400
        
        # Get Cloudflare configuration
        account_id = current_app.config.get('CLOUDFLARE_ACCOUNT_ID')
        api_token = current_app.config.get('CLOUDFLARE_API_TOKEN')
        
        if not account_id or not api_token:
            return jsonify({'error': 'Cloudflare configuration not found'}), 500
        
        # Request direct upload URL from Cloudflare
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/images/v2/direct_upload"
        headers = {
            'Authorization': f'Bearer {api_token}'
        }
        
        # Prepare metadata for the upload
        metadata = {
            'file_id': str(file_id),
            'filename': filename,
            'uploaded_by': str(user_id),
            'upload_time': datetime.datetime.now().isoformat(),
            'is_modify': is_modify
        }
        
        # For modifications, include the old image ID
        if is_modify:
            metadata['replaced_image_id'] = page.object_id
            metadata['modify_time'] = datetime.datetime.now().isoformat()
        
        # Use multipart/form-data format as required by Cloudflare API
        # Cloudflare requires multipart/form-data, so we use files parameter with text values
        form_data = {
            'metadata': (None, json.dumps(metadata)),  # Text field in multipart form
            'requireSignedURLs': (None, 'false'),      # Disable signed URLs temporarily for testing
            'expiry': (None, (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%SZ'))  # 30 minutes in correct format
        }
        
        # Get direct upload URL from Cloudflare using multipart/form-data
        response = requests.post(url, headers=headers, files=form_data)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                upload_url = result['result']['uploadURL']
                upload_id = result['result']['id']
                
                return jsonify({
                    'upload_url': upload_url,
                    'upload_id': upload_id,
                    'file_id': file_id,
                    'is_modify': is_modify,
                    'old_object_id': page.object_id if is_modify else None,
                    'message': 'Direct upload URL generated successfully'
                })
            else:
                return jsonify({'error': 'Failed to generate direct upload URL', 'details': result}), 500
        else:
            return jsonify({'error': f'Cloudflare API error: {response.status_code}', 'details': response.text}), 500
        
    except Exception as e:
        logger.error(f"Error generating direct upload URL: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/file/<int:file_id>/confirm-upload', methods=['POST'])
@jwt_required(locations=['headers','cookies'])
def confirm_direct_upload(file_id):
    """
    Confirm that a direct upload to Cloudflare was successful and update the database
    
    This endpoint should be called after the client successfully uploads directly to Cloudflare
    
    Path parameter:
    - file_id: ID of the file
    
    Request body:
    - upload_id: The upload ID returned from the direct upload URL request
    - cloudflare_id: The final image ID returned by Cloudflare after successful upload
    """
    try:
        # Check user permissions
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user or user.role_id not in [1, 2, 999]:  # Admin, reviewer, or developer only
            return jsonify({'error': 'Permission denied. Admin or reviewer role required.'}), 403
        
        # Get the file
        page = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
        if not page:
            return jsonify({'error': 'File not found'}), 404
        
        # Get request data
        request_data = request.json
        if not request_data:
            return jsonify({'error': 'Request body is required'}), 400
        
        upload_id = request_data.get('upload_id', '')
        cloudflare_id = request_data.get('cloudflare_id', '')
        
        if not upload_id or not cloudflare_id:
            return jsonify({'error': 'upload_id and cloudflare_id are required'}), 400
        
        # Verify the upload was successful by checking Cloudflare
        account_id = current_app.config.get('CLOUDFLARE_ACCOUNT_ID')
        api_token = current_app.config.get('CLOUDFLARE_API_TOKEN')
        
        if not account_id or not api_token:
            return jsonify({'error': 'Cloudflare configuration not found'}), 500
        
        # Verify the image exists in Cloudflare
        verify_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/images/v1/{cloudflare_id}"
        headers = {
            'Authorization': f'Bearer {api_token}'
        }
        
        verify_response = requests.get(verify_url, headers=headers)
        
        if verify_response.status_code == 200:
            verify_result = verify_response.json()
            if verify_result.get('success'):
                # Update the page with the new object_id
                page.object_id = cloudflare_id
                page.updated_at = datetime.datetime.now()
                db.session.commit()
                
                return jsonify({
                    'message': 'Image upload confirmed and database updated successfully',
                    'object_id': cloudflare_id,
                    'file_id': file_id
                })
            else:
                return jsonify({'error': 'Image verification failed', 'details': verify_result}), 400
        else:
            return jsonify({'error': f'Failed to verify image upload: {verify_response.status_code}'}), 400
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error confirming direct upload: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/file/<int:file_id>/r2-exists', methods=['GET'])
@jwt_required(locations=['headers','cookies'])
def check_r2_file_exists(file_id):
    """
    Quick check if R2 file exists for a given file_id
    Used by frontend to determine UI state (clickable vs upload)
    """
    try:
        # Check user permissions
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get the file
        page = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
        if not page:
            return jsonify({'error': 'File not found'}), 404
        
        # Generate the expected R2 object key for this file
        # We'll check common image extensions
        image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf']
        
        r2_exists = False
        existing_object_key = None
        
        # Check if there's a pattern we can use from the page name
        page_name = page.name or f"file_{file_id}"
        
        for ext in image_extensions:
            # Generate object key with this extension
            test_filename = f"{page_name}{ext}"
            test_object_key = generate_r2_object_key(file_id, test_filename, is_page_detail=False)
            
            # Check if this object exists
            if check_r2_object_exists(test_object_key):
                r2_exists = True
                existing_object_key = test_object_key
                break
        
        return jsonify({
            'file_id': file_id,
            'r2_exists': r2_exists,
            'object_key': existing_object_key,
            'has_legacy_cloudflare_image': bool(page.object_id and page.object_id.strip())
        })
        
    except Exception as e:
        logger.error(f"Error checking R2 file existence: {str(e)}")
        return jsonify({'error': str(e)}), 500

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
        request_data = request.json
        if not request_data or 'file_ids' not in request_data:
            return jsonify({'error': 'file_ids array is required'}), 400
        
        file_ids = request_data['file_ids']
        if not isinstance(file_ids, list):
            return jsonify({'error': 'file_ids must be an array'}), 400
        
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
                
                # Check R2 existence
                page_name = page.name or f"file_{file_id}"
                image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf']
                
                r2_exists = False
                existing_object_key = None
                
                for ext in image_extensions:
                    test_filename = f"{page_name}{ext}"
                    test_object_key = generate_r2_object_key(file_id, test_filename, is_page_detail=False)
                    
                    if check_r2_object_exists(test_object_key):
                        r2_exists = True
                        existing_object_key = test_object_key
                        break
                
                results[str(file_id)] = {
                    'r2_exists': r2_exists,
                    'object_key': existing_object_key,
                    'has_legacy_cloudflare_image': bool(page.object_id and page.object_id.strip())
                }
                
            except Exception as e:
                results[str(file_id)] = {
                    'r2_exists': False,
                    'error': str(e)
                }
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Error in batch R2 check: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_contents_bp.route('/debug/cloudflare', methods=['GET'])
@jwt_required(locations=['headers','cookies'])
def debug_cloudflare():
    """
    Debug endpoint to test Cloudflare API credentials
    Only accessible by developers (role_id = 999)
    """
    try:
        # Check user permissions - only developers can access this
        user_id = get_jwt_identity()
        user = Users.query.get(user_id)
        
        if not user or user.role_id != 999:  # Developer only
            return jsonify({'error': 'Permission denied. Developer role required.'}), 403
        
        # Get Cloudflare configuration
        account_id = current_app.config.get('CLOUDFLARE_ACCOUNT_ID')
        api_token = current_app.config.get('CLOUDFLARE_API_TOKEN')
        account_hash = current_app.config.get('CLOUDFLARE_ACCOUNT_HASH')
        signing_key = current_app.config.get('CLOUDFLARE_SIGNING_KEY')
        
        debug_info = {
            'config_loaded': {
                'account_id': account_id[:10] + '...' if account_id else None,
                'api_token_length': len(api_token) if api_token else 0,
                'account_hash': account_hash[:10] + '...' if account_hash else None,
                'signing_key_length': len(signing_key) if signing_key else 0
            },
            'api_tests': {}
        }
        
        if not account_id or not api_token:
            debug_info['api_tests']['error'] = 'Missing Cloudflare configuration'
            return jsonify(debug_info)
        
        headers = {
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json'
        }
        
        # Test 1: List images (basic authentication test)
        list_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/images/v1"
        try:
            list_response = requests.get(list_url, headers=headers, timeout=10)
            debug_info['api_tests']['list_images'] = {
                'status_code': list_response.status_code,
                'success': list_response.status_code == 200,
                'response_snippet': list_response.text[:200] if list_response.text else None
            }
        except Exception as e:
            debug_info['api_tests']['list_images'] = {
                'error': str(e)
            }
        
        # Test 2: Test direct upload endpoint (the one that's failing)
        direct_upload_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/images/v2/direct_upload"
        form_data = {
            'metadata': (None, json.dumps({'test': 'debug'})),
            'requireSignedURLs': (None, 'false'),
            'expiry': (None, (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%SZ'))
        }
        
        try:
            # Remove Content-Type header for form data
            form_headers = {
                'Authorization': f'Bearer {api_token}'
            }
            direct_response = requests.post(direct_upload_url, headers=form_headers, files=form_data, timeout=10)
            debug_info['api_tests']['direct_upload'] = {
                'status_code': direct_response.status_code,
                'success': direct_response.status_code == 200,
                'response_snippet': direct_response.text[:200] if direct_response.text else None
            }
        except Exception as e:
            debug_info['api_tests']['direct_upload'] = {
                'error': str(e)
            }
        
        # Test 3: Get account info (to verify account access)
        account_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
        try:
            account_response = requests.get(account_url, headers=headers, timeout=10)
            debug_info['api_tests']['account_info'] = {
                'status_code': account_response.status_code,
                'success': account_response.status_code == 200,
                'response_snippet': account_response.text[:200] if account_response.text else None
            }
        except Exception as e:
            debug_info['api_tests']['account_info'] = {
                'error': str(e)
            }
        
        # Test 4: Check Images account status and limits
        images_stats_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/images/v1/stats"
        try:
            stats_response = requests.get(images_stats_url, headers=headers, timeout=10)
            debug_info['api_tests']['images_stats'] = {
                'status_code': stats_response.status_code,
                'success': stats_response.status_code == 200,
                'response_snippet': stats_response.text[:200] if stats_response.text else None
            }
        except Exception as e:
            debug_info['api_tests']['images_stats'] = {
                'error': str(e)
            }
        
        return jsonify(debug_info)
        
    except Exception as e:
        logger.error(f"Error in debug cloudflare: {str(e)}")
        return jsonify({'error': str(e)}), 500

#endregion
