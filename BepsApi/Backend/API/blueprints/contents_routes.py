"""
Contents routes - Main blueprint module

This module organizes the contents routes into separate logical components
while maintaining the same API endpoints. This is similar to partial classes in C#.

The blueprint is split into the following modules:
- hierarchy_routes: Hierarchy navigation, paths, channels, folders lookup
- channel_folder_routes: Channel and folder management (CRUD operations)
- file_routes: File upload, download, delete operations
- r2_routes: R2 storage operations and image handling
- page_detail_routes: Page detail specific operations
- content_manager_routes: Content management specific operations
"""

import os
import logging
from flask import Blueprint
from log_config import get_content_logger

# Create the main contents blueprint
api_contents_bp = Blueprint('contents', __name__)

# Initialize logger
logger = get_content_logger()

# Import and register all route modules
def register_all_routes():
    """Register all route modules to the main blueprint"""
    try:
        # Import route registration functions
        from .contents.hierarchy_routes import register_hierarchy_routes
        from .contents.channel_folder_routes import register_channel_folder_routes
        from .contents.file_routes import register_file_routes
        from .contents.page_detail_routes import register_page_detail_routes
        from .contents.r2_routes import register_r2_routes
        from .contents.content_manager_routes import register_content_manager_routes

        # Import NEW route modules for content manager refactoring
        from .contents.additional_content_routes import register_additional_content_routes
        from .contents.pending_approve_routes import register_pending_approve_routes
        from .contents.rename_routes import register_rename_routes

        # Register route modules
        register_hierarchy_routes(api_contents_bp)
        register_channel_folder_routes(api_contents_bp)
        register_file_routes(api_contents_bp)
        register_page_detail_routes(api_contents_bp)
        register_r2_routes(api_contents_bp)
        register_content_manager_routes(api_contents_bp)

        # Register NEW route modules
        register_additional_content_routes(api_contents_bp)
        register_pending_approve_routes(api_contents_bp)
        register_rename_routes(api_contents_bp)

        logger.info("Successfully registered all contents routes (including refactored routes)")

    except ImportError as e:
        logger.error(f"Failed to import route modules: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to register routes: {str(e)}")
        raise

# Register all routes when module is imported
register_all_routes()


# Export utility functions for use by other modules
# These are imported from the r2_utils module
def get_r2_client():
    """Get R2 client - imported from r2_utils"""
    from .contents.r2_utils import get_r2_client as _get_r2_client
    return _get_r2_client()

def generate_r2_signed_url(object_key, expires_in=3600, method='GET'):
    """Generate R2 signed URL - imported from r2_utils"""
    from .contents.r2_utils import generate_r2_signed_url as _generate_r2_signed_url
    return _generate_r2_signed_url(object_key, expires_in, method)

def check_r2_object_exists(object_key):
    """Check R2 object existence - imported from r2_utils"""
    from .contents.r2_utils import check_r2_object_exists as _check_r2_object_exists
    return _check_r2_object_exists(object_key)

def delete_r2_object(object_key):
    """Delete R2 object - imported from r2_utils"""
    from .contents.r2_utils import delete_r2_object as _delete_r2_object
    return _delete_r2_object(object_key)

def generate_r2_object_key(file_id, filename, is_page_detail=False, page_detail_name=None):
    """Generate R2 object key - imported from r2_utils"""
    from .contents.r2_utils import generate_r2_object_key as _generate_r2_object_key
    return _generate_r2_object_key(file_id, filename, is_page_detail, page_detail_name) 