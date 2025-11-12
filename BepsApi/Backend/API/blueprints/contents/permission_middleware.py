"""
Permission middleware for content management

This module provides permission checking functions and decorators for:
- 책임자 (Category Manager/Supervisor) - Manages entire category
- 실무자 (Page Manager/Worker) - Manages individual page

Business Rules:
- 책임자 can upload to any page in their category
- 책임자 can approve updates (click 업데이트 button)
- 실무자 can only upload to their assigned page
- 실무자 cannot approve updates
"""

import logging
from functools import wraps
from flask import jsonify, request, g
from flask_jwt_extended import get_jwt_identity
from extensions import db
from models import ContentManager, ContentRelPages, ContentRelFolders, Users
from log_config import get_content_logger

# Initialize logger
logger = get_content_logger()


def get_current_user():
    """
    Get the current authenticated user from JWT

    Returns:
        User object or None
    """
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return None

        user = Users.query.filter_by(id=user_id, is_deleted=False).first()
        return user
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        return None


def get_user_managed_categories(user_id):
    """
    Get list of category IDs managed by user (as 책임자)

    Args:
        user_id: User ID

    Returns:
        List of category (folder) IDs
    """
    try:
        # Find all ContentManager records where user is assigned as folder manager
        managers = ContentManager.query.filter_by(type='folder').join(
            ContentManager.assignee
        ).filter_by(user_id=user_id).all()

        category_ids = [m.folder_id for m in managers if m.folder_id is not None]
        return category_ids
    except Exception as e:
        logger.error(f"Error getting managed categories for user {user_id}: {str(e)}")
        return []


def get_user_managed_pages(user_id):
    """
    Get list of page IDs managed by user (as 실무자)

    Args:
        user_id: User ID

    Returns:
        List of page (file) IDs
    """
    try:
        # Find all ContentManager records where user is assigned as file manager
        managers = ContentManager.query.filter_by(type='file').join(
            ContentManager.assignee
        ).filter_by(user_id=user_id).all()

        page_ids = [m.file_id for m in managers if m.file_id is not None]
        return page_ids
    except Exception as e:
        logger.error(f"Error getting managed pages for user {user_id}: {str(e)}")
        return []


def is_category_manager(user_id, category_id):
    """
    Check if user is 책임자 (category manager) for given category

    Args:
        user_id: User ID
        category_id: Category (folder) ID

    Returns:
        True if user is category manager, False otherwise
    """
    try:
        manager = ContentManager.query.filter_by(
            type='folder',
            folder_id=category_id
        ).join(
            ContentManager.assignee
        ).filter_by(user_id=user_id).first()

        return manager is not None
    except Exception as e:
        logger.error(f"Error checking category manager: {str(e)}")
        return False

def is_developer(user_id):
    """
    Check if user has developer role

    Args:
        user_id: User ID
        """
    try:
        user = Users.query.filter_by(id=user_id, is_deleted=False).first()
        return user is not None and user.role_id in [1,2,999]
    except Exception as e:
        logger.error(f"Error checking developer role: {str(e)}")
        return False
def is_page_manager(user_id, page_id):
    """
    Check if user is 실무자 (page manager) for given page

    Args:
        user_id: User ID
        page_id: Page (file) ID

    Returns:
        True if user is page manager, False otherwise
    """
    try:
        manager = ContentManager.query.filter_by(
            type='file',
            file_id=page_id
        ).join(
            ContentManager.assignee
        ).filter_by(user_id=user_id).first()

        return manager is not None
    except Exception as e:
        logger.error(f"Error checking page manager: {str(e)}")
        return False


def can_upload_to_page(user_id, page_id):
    """
    Check if user can upload content to a page

    User can upload if:
    - They are 실무자 (page manager) for this page, OR
    - They are 책임자 (category manager) for the page's parent category

    Args:
        user_id: User ID
        page_id: Page (file) ID

    Returns:
        True if user can upload, False otherwise
    """
    try:
        if is_developer(user_id):
            return True
        # Check if user is page manager
        if is_page_manager(user_id, page_id):
            return True

        # Check if user is category manager of the page's category
        page = ContentRelPages.query.filter_by(id=page_id, is_deleted=False).first()
        if not page:
            logger.warning(f"Page {page_id} not found")
            return False

        # Get the page's category (folder_id)
        category_id = page.folder_id
        if category_id and is_category_manager(user_id, category_id):
            return True

        return False
    except Exception as e:
        logger.error(f"Error checking upload permission: {str(e)}")
        return False


def can_approve_update(user_id, page_id):
    """
    Check if user can approve updates (click 업데이트 button)

    Only 책임자 (category manager) can approve updates

    Args:
        user_id: User ID
        page_id: Page (file) ID

    Returns:
        True if user can approve, False otherwise
    """
    try:
        if is_developer(user_id):
            return True
        # Only category managers can approve
        page = ContentRelPages.query.filter_by(id=page_id, is_deleted=False).first()
        if not page:
            logger.warning(f"Page {page_id} not found")
            return False

        category_id = page.folder_id
        return category_id and is_category_manager(user_id, category_id)
    except Exception as e:
        logger.error(f"Error checking approve permission: {str(e)}")
        return False


def get_page_category_id(page_id):
    """
    Get the category (folder) ID for a given page

    Args:
        page_id: Page ID

    Returns:
        Category ID or None
    """
    try:
        page = ContentRelPages.query.filter_by(id=page_id, is_deleted=False).first()
        return page.folder_id if page else None
    except Exception as e:
        logger.error(f"Error getting page category: {str(e)}")
        return None


# ========== Decorators ==========

def require_upload_permission(page_id_param='page_id'):
    """
    Decorator to require upload permission for a page

    Args:
        page_id_param: Name of the parameter containing page_id (default: 'page_id')

    Usage:
        @require_upload_permission()
        def upload_to_page(page_id):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({'error': 'Authentication required'}), 401

            # Get page_id from kwargs or view_args
            page_id = kwargs.get(page_id_param) or request.view_args.get(page_id_param)
            if not page_id:
                return jsonify({'error': f'Missing {page_id_param} parameter'}), 400

            if not can_upload_to_page(user.id, page_id):
                return jsonify({
                    'error': '업로드 권한이 없습니다. 이 페이지의 실무자이거나 상위 카테고리의 책임자여야 합니다.'
                }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_approve_permission(page_id_param='page_id'):
    """
    Decorator to require approval permission (책임자 only)

    Args:
        page_id_param: Name of the parameter containing page_id (default: 'page_id')

    Usage:
        @require_approve_permission()
        def approve_update(page_id):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({'error': 'Authentication required'}), 401

            # Get page_id from kwargs or view_args
            page_id = kwargs.get(page_id_param) or request.view_args.get(page_id_param)
            if not page_id:
                return jsonify({'error': f'Missing {page_id_param} parameter'}), 400

            if not can_approve_update(user.id, page_id):
                return jsonify({
                    'error': '승인 권한이 없습니다. 이 페이지가 속한 카테고리의 책임자여야 합니다.'
                }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_category_manager(category_id_param='category_id'):
    """
    Decorator to require category manager (책임자) permission

    Args:
        category_id_param: Name of the parameter containing category_id (default: 'category_id')

    Usage:
        @require_category_manager()
        def manage_category(category_id):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({'error': 'Authentication required'}), 401

            # Get category_id from kwargs or view_args
            category_id = kwargs.get(category_id_param) or request.view_args.get(category_id_param)
            if not category_id:
                return jsonify({'error': f'Missing {category_id_param} parameter'}), 400

            if not is_category_manager(user.id, category_id):
                return jsonify({
                    'error': '카테고리 관리 권한이 없습니다. 이 카테고리의 책임자여야 합니다.'
                }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_page_manager(page_id_param='page_id'):
    """
    Decorator to require page manager (실무자) permission

    Args:
        page_id_param: Name of the parameter containing page_id (default: 'page_id')

    Usage:
        @require_page_manager()
        def manage_page(page_id):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({'error': 'Authentication required'}), 401

            # Get page_id from kwargs or view_args
            page_id = kwargs.get(page_id_param) or request.view_args.get(page_id_param)
            if not page_id:
                return jsonify({'error': f'Missing {page_id_param} parameter'}), 400

            if not is_page_manager(user.id, page_id):
                return jsonify({
                    'error': '페이지 관리 권한이 없습니다. 이 페이지의 실무자여야 합니다.'
                }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator
