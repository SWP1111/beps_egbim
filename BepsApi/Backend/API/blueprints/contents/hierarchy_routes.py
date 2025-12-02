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
from blueprints.contents.r2_utils import rename_hierarchy_r2_objects, generate_r2_object_key

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
                        'channel_id': category.channel_id,
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
                            'folder_id': page.folder_id,
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

    @api_contents_bp.route('/hierarchy/channel/<int:channel_id>', methods=['PUT'])
    def update_channel(channel_id):
        """
        Update a channel's name

        Request body:
        {
            "name": "New Channel Name"
        }
        """
        try:
            data = request.get_json()

            if not data or 'name' not in data:
                return jsonify({'error': 'Missing name in request body'}), 400

            new_name = data['name'].strip()
            if not new_name:
                return jsonify({'error': 'Name cannot be empty'}), 400

            # Get the channel
            channel = ContentRelChannels.query.filter_by(
                id=channel_id,
                is_deleted=False
            ).first()

            if not channel:
                return jsonify({'error': 'Channel not found'}), 404

            # Check if name already exists (excluding current channel)
            existing = ContentRelChannels.query.filter(
                ContentRelChannels.name == new_name,
                ContentRelChannels.id != channel_id,
                ContentRelChannels.is_deleted == False
            ).first()

            if existing:
                return jsonify({'error': '같은 이름의 탭이 이미 존재합니다'}), 400

            # Store old name for R2 renaming
            old_name = channel.name

            # Update the channel
            channel.name = new_name
            channel.updated_at = datetime.datetime.now()

            db.session.commit()

            logger.info(f"Channel {channel_id} name updated to '{new_name}'")

            # Rename R2 objects to match new channel name
            r2_result = rename_hierarchy_r2_objects(
                old_name=old_name,
                new_name=new_name,
                hierarchy_type='channel',
                parent_path=''
            )

            if not r2_result['success']:
                logger.warning(f"R2 rename had errors for channel {channel_id}: {r2_result['errors']}")

            # Update object_id for all pages under this channel
            try:
                folders = ContentRelFolders.query.filter_by(
                    channel_id=channel_id,
                    is_deleted=False
                ).all()

                for folder in folders:
                    pages = ContentRelPages.query.filter_by(
                        folder_id=folder.id,
                        is_deleted=False
                    ).all()

                    for page in pages:
                        # Regenerate object_id
                        new_object_id = generate_r2_object_key(
                            file_id=page.id,
                            filename=page.name,
                            is_page_detail=False
                        )
                        page.object_id = new_object_id

                        # Also update page details
                        details = ContentRelPageDetails.query.filter_by(
                            page_id=page.id,
                            is_deleted=False
                        ).all()

                        for detail in details:
                            new_detail_object_id = generate_r2_object_key(
                                file_id=detail.id,
                                filename=detail.name,
                                is_page_detail=True
                            )
                            detail.object_id = new_detail_object_id

                db.session.commit()
                logger.info(f"Updated object_id fields for channel {channel_id}")
            except Exception as e:
                logger.error(f"Error updating object_id fields: {str(e)}")
                # Don't fail the request, just log the error

            return jsonify({
                'success': True,
                'message': 'Channel updated successfully',
                'channel': {
                    'id': channel.id,
                    'name': channel.name,
                    'updated_at': channel.updated_at.isoformat() if channel.updated_at else None
                }
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating channel {channel_id}: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/hierarchy/folder/<int:folder_id>', methods=['PUT'])
    def update_folder(folder_id):
        """
        Update a folder's name and/or parent channel

        Request body:
        {
            "name": "New Folder Name",
            "channel_id": 123  # Optional: change parent channel
        }
        """
        try:
            data = request.get_json()

            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            # Get the folder
            folder = ContentRelFolders.query.filter_by(
                id=folder_id,
                is_deleted=False,
                parent_id=None  # Only top-level folders (categories)
            ).first()

            if not folder:
                return jsonify({'error': 'Folder not found or not a top-level category'}), 404

            # Store old values for R2 renaming
            old_folder_name = folder.name
            old_channel_id = folder.channel_id

            # Get old channel name for path construction
            old_channel = ContentRelChannels.query.get(old_channel_id)
            old_channel_name = old_channel.name if old_channel else ''

            # Update name if provided
            if 'name' in data:
                new_name = data['name'].strip()
                if not new_name:
                    return jsonify({'error': 'Name cannot be empty'}), 400

                # Check if name already exists in same channel (excluding current folder)
                channel_id = data.get('channel_id', folder.channel_id)
                existing = ContentRelFolders.query.filter(
                    ContentRelFolders.name == new_name,
                    ContentRelFolders.channel_id == channel_id,
                    ContentRelFolders.parent_id == None,
                    ContentRelFolders.id != folder_id,
                    ContentRelFolders.is_deleted == False
                ).first()

                if existing:
                    return jsonify({'error': '같은 탭에 같은 이름의 카테고리가 이미 존재합니다'}), 400

                folder.name = new_name

            # Update channel if provided
            new_channel_name = old_channel_name
            if 'channel_id' in data:
                new_channel_id = int(data['channel_id'])

                # Verify channel exists
                new_channel = ContentRelChannels.query.filter_by(
                    id=new_channel_id,
                    is_deleted=False
                ).first()

                if not new_channel:
                    return jsonify({'error': 'Target channel not found'}), 404

                folder.channel_id = new_channel_id
                new_channel_name = new_channel.name

            folder.updated_at = datetime.datetime.now()

            db.session.commit()

            logger.info(f"Folder {folder_id} updated: name='{folder.name}', channel_id={folder.channel_id}")

            # Rename R2 objects if name or channel changed
            if old_folder_name != folder.name or old_channel_id != folder.channel_id:
                r2_result = rename_hierarchy_r2_objects(
                    old_name=old_folder_name,
                    new_name=folder.name,
                    hierarchy_type='folder',
                    parent_path=old_channel_name if old_channel_id == folder.channel_id else new_channel_name
                )

                if not r2_result['success']:
                    logger.warning(f"R2 rename had errors for folder {folder_id}: {r2_result['errors']}")

                # Update object_id for all pages under this folder
                try:
                    pages = ContentRelPages.query.filter_by(
                        folder_id=folder_id,
                        is_deleted=False
                    ).all()

                    for page in pages:
                        # Regenerate object_id
                        new_object_id = generate_r2_object_key(
                            file_id=page.id,
                            filename=page.name,
                            is_page_detail=False
                        )
                        page.object_id = new_object_id

                        # Also update page details
                        details = ContentRelPageDetails.query.filter_by(
                            page_id=page.id,
                            is_deleted=False
                        ).all()

                        for detail in details:
                            new_detail_object_id = generate_r2_object_key(
                                file_id=detail.id,
                                filename=detail.name,
                                is_page_detail=True
                            )
                            detail.object_id = new_detail_object_id

                    db.session.commit()
                    logger.info(f"Updated object_id fields for folder {folder_id}")
                except Exception as e:
                    logger.error(f"Error updating object_id fields: {str(e)}")
                    # Don't fail the request, just log the error

            return jsonify({
                'success': True,
                'message': 'Folder updated successfully',
                'folder': {
                    'id': folder.id,
                    'name': folder.name,
                    'channel_id': folder.channel_id,
                    'updated_at': folder.updated_at.isoformat() if folder.updated_at else None
                }
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating folder {folder_id}: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/hierarchy/page/<int:page_id>', methods=['PUT'])
    def update_page(page_id):
        """
        Update a page's name and/or parent folder

        Request body:
        {
            "name": "New Page Name",
            "folder_id": 123  # Optional: change parent folder
        }
        """
        try:
            data = request.get_json()

            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            # Get the page
            page = ContentRelPages.query.filter_by(
                id=page_id,
                is_deleted=False
            ).first()

            if not page:
                return jsonify({'error': 'Page not found'}), 404

            # Store old values for R2 renaming
            old_page_name = page.name
            old_folder_id = page.folder_id

            # Get old folder and channel for path construction
            old_folder = ContentRelFolders.query.get(old_folder_id)
            if old_folder:
                old_channel = ContentRelChannels.query.get(old_folder.channel_id)
                old_parent_path = f"{old_channel.name}/{old_folder.name}" if old_channel else old_folder.name
            else:
                old_parent_path = ''

            # Update name if provided
            if 'name' in data:
                new_name = data['name'].strip()
                if not new_name:
                    return jsonify({'error': 'Name cannot be empty'}), 400

                # Check if name already exists in same folder (excluding current page)
                folder_id = data.get('folder_id', page.folder_id)
                existing = ContentRelPages.query.filter(
                    ContentRelPages.name == new_name,
                    ContentRelPages.folder_id == folder_id,
                    ContentRelPages.id != page_id,
                    ContentRelPages.is_deleted == False
                ).first()

                if existing:
                    return jsonify({'error': '같은 카테고리에 같은 이름의 페이지가 이미 존재합니다'}), 400

                page.name = new_name

            # Update folder if provided
            new_parent_path = old_parent_path
            if 'folder_id' in data:
                new_folder_id = int(data['folder_id'])

                # Verify folder exists
                new_folder = ContentRelFolders.query.filter_by(
                    id=new_folder_id,
                    is_deleted=False
                ).first()

                if not new_folder:
                    return jsonify({'error': 'Target folder not found'}), 404

                page.folder_id = new_folder_id

                # Get new parent path
                new_channel = ContentRelChannels.query.get(new_folder.channel_id)
                new_parent_path = f"{new_channel.name}/{new_folder.name}" if new_channel else new_folder.name

            page.updated_at = datetime.datetime.now()

            db.session.commit()

            logger.info(f"Page {page_id} updated: name='{page.name}', folder_id={page.folder_id}")

            # Rename R2 objects if name or folder changed
            if old_page_name != page.name or old_folder_id != page.folder_id:
                r2_result = rename_hierarchy_r2_objects(
                    old_name=old_page_name,
                    new_name=page.name,
                    hierarchy_type='page',
                    parent_path=old_parent_path if old_folder_id == page.folder_id else new_parent_path
                )

                if not r2_result['success']:
                    logger.warning(f"R2 rename had errors for page {page_id}: {r2_result['errors']}")

                # Update object_id for the page and its details
                try:
                    # Update page object_id
                    new_object_id = generate_r2_object_key(
                        file_id=page.id,
                        filename=page.name,
                        is_page_detail=False
                    )
                    page.object_id = new_object_id

                    # Also update page details
                    details = ContentRelPageDetails.query.filter_by(
                        page_id=page.id,
                        is_deleted=False
                    ).all()

                    for detail in details:
                        new_detail_object_id = generate_r2_object_key(
                            file_id=detail.id,
                            filename=detail.name,
                            is_page_detail=True
                        )
                        detail.object_id = new_detail_object_id

                    db.session.commit()
                    logger.info(f"Updated object_id fields for page {page_id}")
                except Exception as e:
                    logger.error(f"Error updating object_id fields: {str(e)}")
                    # Don't fail the request, just log the error

            return jsonify({
                'success': True,
                'message': 'Page updated successfully',
                'page': {
                    'id': page.id,
                    'name': page.name,
                    'folder_id': page.folder_id,
                    'updated_at': page.updated_at.isoformat() if page.updated_at else None
                }
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating page {page_id}: {str(e)}")
            return jsonify({'error': str(e)}), 500 