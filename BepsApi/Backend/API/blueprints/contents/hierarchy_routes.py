"""
Hierarchy-related routes for content management

This module handles:
- Content hierarchy retrieval
- Path building and navigation
- Channel and folder children lookup
"""

import logging
import datetime
from flask import Blueprint, jsonify, request
from extensions import db
from models import ContentRelPages, ContentRelFolders, ContentRelChannels, ContentRelPageDetails
from services.content_hierarchy_service import ContentHierarchyService
from log_config import get_content_logger

# Initialize logger
logger = get_content_logger()


def register_hierarchy_routes(api_contents_bp):
    """Register all hierarchy-related routes to the blueprint"""
    
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

    @api_contents_bp.route('/hierarchy/channel/<int:channel_id>', methods=['GET'])
    def get_channel_hierarchy(channel_id):
        """
        Get the hierarchy for a specific channel with filtering support
        
        Optional query parameters:
        - filters: JSON string with filter configuration
        """
        try:
            import json
            from urllib.parse import unquote
            
            # Get filters from query parameters
            filters_param = request.args.get('filters', '{}')
            try:
                filters = json.loads(unquote(filters_param))
            except json.JSONDecodeError:
                filters = {}
            
            # Use the hierarchy service
            service = ContentHierarchyService()
            hierarchy = service.get_channel_hierarchy(channel_id, filters)
            
            return jsonify(hierarchy)
        except Exception as e:
            logger.error(f"Error getting channel hierarchy: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/hierarchy-with-managers', methods=['GET'])
    def get_hierarchy_with_managers():
        """
        Get the full content hierarchy with manager assignments

        Returns structured data for the unified Content/Manager Admin table:
        - Channels (탭)
        - Categories (카테고리) with 책임자 (category managers)
        - Pages (페이지) with 실무자 (page managers)

        Response is sorted by: channel → category → page
        """
        try:
            from models import ContentManager, Assignees

            # Get all channels
            channels = ContentRelChannels.query.filter_by(is_deleted=False).order_by(ContentRelChannels.name).all()

            result = {
                'channels': []
            }

            for channel in channels:
                channel_data = {
                    'id': channel.id,
                    'name': channel.name,
                    'description': channel.description,
                    'categories': []
                }

                # Get top-level folders (categories) for this channel
                categories = ContentRelFolders.query.filter_by(
                    channel_id=channel.id,
                    parent_id=None,
                    is_deleted=False
                ).order_by(ContentRelFolders.name).all()

                for category in categories:
                    # Get category manager (책임자)
                    category_manager = None
                    manager_record = ContentManager.query.filter_by(
                        type='folder',
                        folder_id=category.id
                    ).first()

                    if manager_record and manager_record.assignee_id:
                        assignee = Assignees.query.get(manager_record.assignee_id)
                        if assignee:
                            category_manager = {
                                'name': assignee.name,
                                'position': assignee.position,
                                'user_id': assignee.user_id
                            }

                    category_data = {
                        'id': category.id,
                        'name': category.name,
                        'description': category.description,
                        'manager': category_manager,  # 책임자
                        'pages': []
                    }

                    # Get pages for this category
                    pages = ContentRelPages.query.filter_by(
                        folder_id=category.id,
                        is_deleted=False
                    ).order_by(ContentRelPages.name).all()

                    for page in pages:
                        # Get page manager (실무자)
                        page_manager = None
                        page_manager_record = ContentManager.query.filter_by(
                            type='file',
                            file_id=page.id
                        ).first()

                        if page_manager_record and page_manager_record.assignee_id:
                            assignee = Assignees.query.get(page_manager_record.assignee_id)
                            if assignee:
                                page_manager = {
                                    'name': assignee.name,
                                    'position': assignee.position,
                                    'user_id': assignee.user_id
                                }

                        # Check if page has pending content
                        from models import PendingContent
                        has_pending = PendingContent.query.filter_by(
                            content_type='page',
                            page_id=page.id
                        ).first() is not None

                        page_data = {
                            'id': page.id,
                            'name': page.name,
                            'description': page.description,
                            'object_id': page.object_id,
                            'manager': page_manager,  # 실무자
                            'has_pending': has_pending,
                            'created_at': page.created_at.isoformat() if page.created_at else None,
                            'updated_at': page.updated_at.isoformat() if page.updated_at else None
                        }

                        category_data['pages'].append(page_data)

                    channel_data['categories'].append(category_data)

                result['channels'].append(channel_data)

            return jsonify(result)

        except Exception as e:
            logger.error(f"Error getting hierarchy with managers: {str(e)}")
            return jsonify({'error': str(e)}), 500 