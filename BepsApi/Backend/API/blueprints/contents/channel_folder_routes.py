"""
Channel and Folder management routes

This module handles:
- Channel creation and deletion
- Folder creation and deletion
- Access control and permissions
"""

import logging
import datetime
from datetime import timezone
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import ContentRelChannels, ContentRelFolders, ContentRelPages, Users, ContentManager, Assignees
from log_config import get_content_logger
from werkzeug.utils import secure_filename

# Initialize logger
logger = get_content_logger()


def register_channel_folder_routes(api_contents_bp):
    """Register all channel and folder management routes to the blueprint"""
    
    @api_contents_bp.route('/channels', methods=['GET'])
    def get_channels():
        """
        Get all channels
        """
        try:
            channels = ContentRelChannels.query.filter_by(is_deleted=False).all()
            return jsonify({
                'channels': [channel.to_dict() for channel in channels]
            })
        except Exception as e:
            logger.error(f"Error getting channels: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/user-accessible', methods=['GET'])
    def get_user_accessible_content():
        """
        Get content that the user has access to
        
        Query parameters:
        - user_id: The user ID to check permissions for
        """
        try:
            user_id = request.args.get('user_id')
            if not user_id:
                return jsonify({'error': 'Missing user_id parameter'}), 400
            
            # Get user's accessible content from ContentManager table
            managers = ContentManager.query.filter_by(user_id=user_id).all()
            
            folder_ids = []
            file_ids = []
            
            for manager in managers:
                if manager.folder_id:
                    folder_ids.append(manager.folder_id)
                if manager.file_id:
                    file_ids.append(manager.file_id)
            
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
        Check if a user has access to a specific channel
        
        Query parameters:
        - user_id: The user ID to check permissions for
        """
        try:
            user_id = request.args.get('user_id')
            if not user_id:
                return jsonify({'error': 'Missing user_id parameter'}), 400
            
            # Check if user has any folder access in this channel
            has_access = db.session.query(ContentManager).join(
                ContentRelFolders, ContentManager.folder_id == ContentRelFolders.id
            ).join(
                ContentRelChannels, ContentRelFolders.channel_id == ContentRelChannels.id
            ).join(
                Assignees, ContentManager.assignee_id == Assignees.id
            ).filter(
                Assignees.user_id == user_id,
                ContentRelChannels.id == channel_id,
                ContentRelChannels.is_deleted == False
            ).first() is not None
            
            return jsonify({
                'hasAccess': has_access
            })
        except Exception as e:
            logger.error(f"Error checking channel accessibility: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/channel', methods=['POST'])
    @jwt_required(locations=['headers','cookies'])
    def create_channel():
        """
        Create a new channel
        """
        try:
            current_user_id = get_jwt_identity()
            data = request.get_json()
            
            if not data or 'name' not in data:
                return jsonify({'error': 'Missing channel name'}), 400
            
            # Check if user has permission (admin or super admin)
            user = Users.query.filter_by(id=current_user_id).first()
            if not user or user.role_id not in [1, 999]:  # 1: admin, 999: super admin
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            # Create new channel
            new_channel = ContentRelChannels(
                name=data['name'],
                description=data.get('description', ''),
                created_at=datetime.datetime.now(timezone.utc),
                updated_at=datetime.datetime.now(timezone.utc)
            )
            
            db.session.add(new_channel)
            db.session.commit()
            
            logger.info(f"User {current_user_id} created channel: {new_channel.name}")
            
            return jsonify({
                'message': 'Channel created successfully',
                'channel': new_channel.to_dict()
            }), 201
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating channel: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/channel/<int:channel_id>', methods=['DELETE'])
    @jwt_required(locations=['headers','cookies'])
    def delete_channel(channel_id):
        """
        Delete a channel (soft delete)
        """
        try:
            current_user_id = get_jwt_identity()
            
            # Check if user has permission (admin or super admin)
            user = Users.query.filter_by(id=current_user_id).first()
            if not user or user.role_id not in [1, 999]:  # 1: admin, 999: super admin
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            # Find the channel
            channel = ContentRelChannels.query.filter_by(id=channel_id, is_deleted=False).first()
            if not channel:
                return jsonify({'error': 'Channel not found'}), 404
            
            # Soft delete the channel
            channel.is_deleted = True
            channel.updated_at = datetime.datetime.now(timezone.utc)
            
            # Also soft delete all folders and pages in this channel
            folders = ContentRelFolders.query.filter_by(channel_id=channel_id, is_deleted=False).all()
            for folder in folders:
                folder.is_deleted = True
                folder.updated_at = datetime.datetime.now(timezone.utc)
                
                # Soft delete all pages in the folder
                pages = ContentRelPages.query.filter_by(folder_id=folder.id, is_deleted=False).all()
                for page in pages:
                    page.is_deleted = True
                    page.updated_at = datetime.datetime.now(timezone.utc)
            
            db.session.commit()
            
            logger.info(f"User {current_user_id} deleted channel: {channel.name}")
            
            return jsonify({'message': 'Channel deleted successfully'})
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting channel: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/folder', methods=['POST'])
    @jwt_required(locations=['headers','cookies'])
    def create_folder():
        """
        Create a new folder
        """
        try:
            current_user_id = get_jwt_identity()
            data = request.get_json()
            
            if not data or 'name' not in data:
                return jsonify({'error': 'Missing folder name'}), 400
            
            # Check if user has permission (admin, reviewer, or super admin)
            user = Users.query.filter_by(id=current_user_id).first()
            if not user or user.role_id not in [1, 2, 999]:  # 1: admin, 2: reviewer, 999: super admin
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            # Validate required fields
            channel_id = data.get('channel_id')
            parent_id = data.get('parent_id')
            
            if not channel_id and not parent_id:
                return jsonify({'error': 'Either channel_id or parent_id must be provided'}), 400
            
            # If parent_id is provided, get channel_id from parent
            if parent_id:
                parent = ContentRelFolders.query.filter_by(id=parent_id, is_deleted=False).first()
                if not parent:
                    return jsonify({'error': 'Parent folder not found'}), 404
                channel_id = parent.channel_id
            
            # Create new folder
            new_folder = ContentRelFolders(
                parent_id=parent_id,
                channel_id=channel_id,
                name=data['name'],
                description=data.get('description', ''),
                created_at=datetime.datetime.now(timezone.utc),
                updated_at=datetime.datetime.now(timezone.utc)
            )
            
            db.session.add(new_folder)
            db.session.commit()
            
            logger.info(f"User {current_user_id} created folder: {new_folder.name}")
            
            return jsonify({
                'message': 'Folder created successfully',
                'folder': new_folder.to_dict()
            }), 201
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating folder: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/folder/<int:folder_id>', methods=['DELETE'])
    @jwt_required(locations=['headers','cookies'])
    def delete_folder(folder_id):
        """
        Delete a folder (soft delete)
        """
        try:
            current_user_id = get_jwt_identity()
            
            # Check if user has permission (admin, reviewer, or super admin)
            user = Users.query.filter_by(id=current_user_id).first()
            if not user or user.role_id not in [1, 2, 999]:  # 1: admin, 2: reviewer, 999: super admin
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            # Find the folder
            folder = ContentRelFolders.query.filter_by(id=folder_id, is_deleted=False).first()
            if not folder:
                return jsonify({'error': 'Folder not found'}), 404
            
            # Soft delete the folder
            folder.is_deleted = True
            folder.updated_at = datetime.datetime.now(timezone.utc)
            
            # Also soft delete all pages in this folder
            pages = ContentRelPages.query.filter_by(folder_id=folder_id, is_deleted=False).all()
            for page in pages:
                page.is_deleted = True
                page.updated_at = datetime.datetime.now(timezone.utc)
            
            db.session.commit()
            
            logger.info(f"User {current_user_id} deleted folder: {folder.name}")
            
            return jsonify({'message': 'Folder deleted successfully'})
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting folder: {str(e)}")
            return jsonify({'error': str(e)}), 500 