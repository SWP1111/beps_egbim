"""
Content Manager routes

This module handles:
- Content manager permissions
- User access control
- Manager CRUD operations
"""

import logging
import re
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import ContentManager, Users, ContentRelChannels, ContentRelFolders, ContentRelPages,Assignees
from log_config import get_content_logger

# Initialize logger
logger = get_content_logger()


def register_content_manager_routes(api_contents_bp):
    """Register all content manager routes to the blueprint"""
    
    @api_contents_bp.route('/content_manager', methods=['GET'])
    def get_content_managers():
        """
        Get all content managers
        
        Returns a list of content manager entries
        """
        try:
            rows = (db.session.query(ContentManager, Assignees)
                    .outerjoin(Assignees, ContentManager.assignee_id == Assignees.id)
                    .all())
            
            data = []
            for cm, a in rows:
                base = cm.to_dict()
                base['assignee'] = None if a is None else {
                    'id': a.id,
                    'user_id': a.user_id,
                    'name': a.name,
                    'position' : a.position
                }
                data.append(base)
                
            return jsonify(data)
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
            
            assignee = Assignees.query.filter_by(user_id=user_id).first()
            if not assignee:
                prefixes = ('연구원','선임','책임','수석','대리','과장','차장','부장')
                raw = user.position
                s = re.sub(r'\s+', ' ', raw).strip() if raw else ''
                position = ('미지정' if not s else next((p for p in prefixes if s.startswith(p)), re.split(r'[\s(/]', s, 1)[0]))
                assignee = Assignees(user_id=user_id, name=user.name, position=position)
                db.session.add(assignee)
                db.session.flush()  # Flush to get the ID
                
            # Use the actual user ID from the database to ensure consistent casing
            user_id = user.id
            
            # Check for duplicate permission based on type
            if permission_type == 'channel' and 'channel_id' in data:
                channel_id = int(data['channel_id'])
                
                # Verify channel exists
                channel = ContentRelChannels.query.filter_by(id=channel_id, is_deleted=False).first()
                if not channel:
                    return jsonify({'error': f'Channel with ID {channel_id} not found'}), 404
                
                # Check for duplicate - only one manager per content allowed
                duplicate = ContentManager.query.filter_by(
                    type='channel',
                    channel_id=channel_id
                ).first()
                
                if duplicate:
                    return jsonify({'error': f'This channel already has a manager assigned'}), 409
                
                # Create new manager entry
                manager = ContentManager(
                    assignee_id=assignee.id,
                    type=permission_type,
                    channel_id=channel_id
                )
            
            elif permission_type == 'folder' and 'folder_id' in data:
                folder_id = int(data['folder_id'])
                
                # Verify folder exists
                folder = ContentRelFolders.query.filter_by(id=folder_id, is_deleted=False).first()
                if not folder:
                    return jsonify({'error': f'Folder with ID {folder_id} not found'}), 404
                
                # Check for duplicate - only one manager per content allowed
                duplicate = ContentManager.query.filter_by(
                    type='folder',
                    folder_id=folder_id
                ).first()
                
                if duplicate:
                    return jsonify({'error': f'This folder already has a manager assigned'}), 409
                
                # Create new manager entry
                manager = ContentManager(
                    assignee_id=assignee.id,
                    type=permission_type,
                    folder_id=folder_id
                )
            
            elif permission_type == 'file' and 'file_id' in data:
                file_id = int(data['file_id'])
                
                # Verify file exists
                file = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
                if not file:
                    return jsonify({'error': f'File with ID {file_id} not found'}), 404
                
                # Check for duplicate - only one manager per content allowed
                duplicate = ContentManager.query.filter_by(
                    type='file',
                    file_id=file_id
                ).first()
                
                if duplicate:
                    return jsonify({'error': f'This file already has a manager assigned'}), 409
                
                # Create new manager entry
                manager = ContentManager(
                    assignee_id=assignee.id,
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
            
            assignee_id = manager.assignee_id
            should_delete_assignee = False
            if assignee_id is not None:
                other_exists = db.session.query(ContentManager.id).filter(
                    ContentManager.assignee_id == assignee_id,
                    ContentManager.id != manager_id
                ).first()
                should_delete_assignee = (other_exists is None)
                
            db.session.delete(manager)
            
            if should_delete_assignee:
                assignee = Assignees.query.get(assignee_id)
                if assignee:
                    db.session.delete(assignee)
                    
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
        VERSION: 2025-01-11-BACKEND-FIX

        Path parameter:
        - manager_id: ID of the content manager entry to update

        Request body:
        - user_id: ID of the user to add as manager
        - type: Type of permission ('channel', 'folder', or 'file')
        - file_id: ID of the file (when type is 'file')
        - folder_id: ID of the folder (when type is 'folder')
        - channel_id: ID of the channel (when type is 'channel')
        """
        logger.info(f"PUT /content_manager/{manager_id} - VERSION: 2025-01-11-BACKEND-FIX")
        try:
            # Find the manager entry
            manager = ContentManager.query.get(manager_id)
            if not manager:
                return jsonify({'error': f'Content manager entry with ID {manager_id} not found'}), 404
            
            data = request.json

            if not data:
                return jsonify({'error': 'Request body is required'}), 400

            logger.info(f"Request data: {data}")

            # Store original user_id for duplicate checking
            original_assignee_id = manager.assignee_id
            original_type = manager.type
            original_channel_id = manager.channel_id
            original_folder_id = manager.folder_id
            original_file_id = manager.file_id

            # Update type and related IDs FIRST (before any flush)
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

                    manager.channel_id = channel_id

                elif permission_type == 'folder' and 'folder_id' in data:
                    folder_id = int(data['folder_id'])

                    # Verify folder exists
                    folder = ContentRelFolders.query.filter_by(id=folder_id, is_deleted=False).first()
                    if not folder:
                        return jsonify({'error': f'Folder with ID {folder_id} not found'}), 404

                    manager.folder_id = folder_id
                    logger.info(f"Set manager.folder_id = {manager.folder_id}, manager.type = {manager.type}")

                elif permission_type == 'file' and 'file_id' in data:
                    file_id = int(data['file_id'])

                    # Verify file exists
                    file = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
                    if not file:
                        return jsonify({'error': f'File with ID {file_id} not found'}), 404

                    manager.file_id = file_id

                else:
                    # Missing required IDs for the selected type
                    missing_field = 'channel_id' if permission_type == 'channel' else ('folder_id' if permission_type == 'folder' else 'file_id')
                    return jsonify({'error': f'Required field missing: {missing_field}'}), 400

            # Now update user_id if provided (this might flush)
            if 'user_id' in data:
                user_id = data['user_id']
                # Validate user exists with case-insensitive search
                user = Users.query.filter(Users.id.ilike(user_id)).first()
                if not user:
                    return jsonify({'error': f'User with ID {user_id} not found'}), 404
                # Use the actual user ID from the database to ensure consistent casing
                assignee = Assignees.query.filter(Assignees.user_id == user.id).first()
                if not assignee:
                    prefixes = ('연구원','선임','책임','수석','대리','과장','차장','부장')
                    raw = user.position
                    s = re.sub(r'\s+', ' ', raw).strip() if raw else ''
                    position = ('미지정' if not s else next((p for p in prefixes if s.startswith(p)), re.split(r'[\s(/]', s, 1)[0]))
                    assignee = Assignees(user_id=user.id, name=user.name, position=position)
                    db.session.add(assignee)
                    logger.info(f"BEFORE FLUSH: manager.folder_id={manager.folder_id}, manager.file_id={manager.file_id}, manager.channel_id={manager.channel_id}, manager.type={manager.type}")
                    db.session.flush()  # Flush to get the ID
                    logger.info(f"AFTER FLUSH: manager.folder_id={manager.folder_id}, manager.file_id={manager.file_id}")
                user_id = user.id
                manager.assignee_id = assignee.id
                assignee_id = assignee.id
            else:
                assignee_id = original_assignee_id

            # Check for duplicates after type and IDs are set
            if manager.type == 'channel' and manager.channel_id:
                duplicate = ContentManager.query.filter_by(
                    type='channel',
                    channel_id=manager.channel_id
                ).filter(ContentManager.id != manager_id).first()

                if duplicate:
                    return jsonify({'error': f'This channel already has a manager assigned'}), 409

            elif manager.type == 'folder' and manager.folder_id:
                duplicate = ContentManager.query.filter_by(
                    type='folder',
                    folder_id=manager.folder_id
                ).filter(ContentManager.id != manager_id).first()

                if duplicate:
                    return jsonify({'error': f'This folder already has a manager assigned'}), 409

            elif manager.type == 'file' and manager.file_id:
                duplicate = ContentManager.query.filter_by(
                    type='file',
                    file_id=manager.file_id
                ).filter(ContentManager.id != manager_id).first()

                if duplicate:
                    return jsonify({'error': f'This file already has a manager assigned'}), 409
            
            # 수정 전 assignee_id가 더이상 사용되지 않으면 테이블에서 행 제거
            should_delete_assignee = False
            if 'user_id' in data and original_assignee_id is not None and original_assignee_id != assignee_id:
                other_manager_exists = db.session.query(ContentManager.id).filter(
                    ContentManager.assignee_id == original_assignee_id,
                ).first()
                should_delete_assignee = (other_manager_exists is None)
                      
            if should_delete_assignee:
                old_assignee = Assignees.query.get(original_assignee_id)
                if old_assignee:
                    db.session.delete(old_assignee)
                    
            # Save to database
            db.session.commit()
            
            return jsonify(manager.to_dict())
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating content manager: {str(e)}")
            return jsonify({'error': str(e)}), 500