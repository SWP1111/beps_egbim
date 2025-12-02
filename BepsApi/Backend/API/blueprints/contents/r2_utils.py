"""
R2/Cloudflare R2 Storage utility functions

This module provides utility functions for interacting with Cloudflare R2 storage:
- R2 client management
- Object existence checking
- Signed URL generation
- Object key generation
"""

import os
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError, NoCredentialsError
import logging
from flask import current_app
from log_config import get_content_logger
from models import ContentRelPages, ContentRelFolders, ContentRelChannels, ContentRelPageDetails

# Initialize logger
logger = get_content_logger()


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
    Generate a pre-signed URL for R2 object access
    
    Args:
        object_key: The R2 object key
        expires_in: URL expiration time in seconds (default: 1 hour)
        method: HTTP method ('GET' or 'PUT')
    
    Returns:
        Signed URL string
    """
    try:
        r2_client = get_r2_client()
        bucket_name = current_app.config.get('R2_BUCKET_NAME')
        
        if not bucket_name:
            raise ValueError("R2 bucket name not found in configuration")
        
        # Generate signed URL
        if method.upper() == 'GET':
            signed_url = r2_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': object_key},
                ExpiresIn=expires_in
            )
        elif method.upper() == 'PUT':
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
    Check if an object exists in R2 storage
    
    Args:
        object_key: The R2 object key to check
    
    Returns:
        True if object exists, False otherwise
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
    Delete an object from R2 storage
    
    Args:
        object_key: The R2 object key to delete
    
    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        r2_client = get_r2_client()
        bucket_name = current_app.config.get('R2_BUCKET_NAME')
        
        # Delete the object
        r2_client.delete_object(Bucket=bucket_name, Key=object_key)
        logger.info(f"Successfully deleted R2 object: {object_key}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete R2 object {object_key}: {str(e)}")
        return False


def generate_r2_object_key(file_id, filename, is_page_detail=False, page_detail_name=None):
    """
    Generate R2 object key based on content hierarchy

    Args:
        file_id: The file ID (page or page detail)
        filename: The filename
        is_page_detail: Whether this is a page detail
        page_detail_name: Name of the page detail (if applicable)

    Returns:
        Generated R2 object key
    """
    try:
        if is_page_detail:
            # For page details, get the parent page information
            detail = ContentRelPageDetails.query.filter_by(id=file_id, is_deleted=False).first()
            if not detail:
                raise ValueError(f"Page detail with ID {file_id} not found")

            # Get the parent page
            parent_page = ContentRelPages.query.filter_by(id=detail.page_id, is_deleted=False).first()
            if not parent_page:
                raise ValueError(f"Parent page for detail {file_id} not found")

            # Use the parent page's folder hierarchy
            folder_id = parent_page.folder_id
            page_name = parent_page.name
        else:
            # For pages, get the page information
            page = ContentRelPages.query.filter_by(id=file_id, is_deleted=False).first()
            if not page:
                raise ValueError(f"Page with ID {file_id} not found")

            folder_id = page.folder_id
            page_name = page.name

        # Build the path components
        path_components = []

        # Traverse the folder hierarchy
        current_folder_id = folder_id
        while current_folder_id is not None:
            folder = ContentRelFolders.query.filter_by(id=current_folder_id, is_deleted=False).first()
            if not folder:
                break

            # Replace problematic characters for R2 path
            safe_folder_name = folder.name.replace('/', '⁄').replace('\\', '⁄')
            path_components.append(safe_folder_name)

            if folder.parent_id is None:
                # Top-level folder, get the channel
                channel = ContentRelChannels.query.filter_by(id=folder.channel_id, is_deleted=False).first()
                if channel:
                    safe_channel_name = channel.name.replace('/', '⁄').replace('\\', '⁄')
                    path_components.append(safe_channel_name)
                break

            current_folder_id = folder.parent_id

        # Reverse to get correct order (channel -> folders -> page)
        path_components.reverse()

        if is_page_detail:
            # For page details, add page folder (without extension)
            import os as os_module
            page_name_without_ext = os_module.path.splitext(page_name)[0]
            safe_page_name = page_name_without_ext.replace('/', '⁄').replace('\\', '⁄')
            path_components.append(safe_page_name)

        # Add the filename
        safe_filename = filename.replace('/', '⁄').replace('\\', '⁄')
        path_components.append(safe_filename)

        # Join with forward slashes for R2 object key
        object_key = '/'.join(path_components)

        return object_key

    except Exception as e:
        logger.error(f"Error generating R2 object key for file {file_id}: {str(e)}")
        # Fallback to simple key
        return f"files/{file_id}/{filename}"


# ========== Extended R2 Utilities for Content Manager Refactoring ==========

def move_r2_object(source_key, destination_key):
    """
    Move an object from one location to another in R2
    This is implemented as copy + delete

    Args:
        source_key: Source object key
        destination_key: Destination object key

    Returns:
        True if successful, False otherwise
    """
    try:
        r2_client = get_r2_client()
        bucket_name = current_app.config.get('R2_BUCKET_NAME')

        # Copy the object to new location
        copy_source = {'Bucket': bucket_name, 'Key': source_key}
        r2_client.copy_object(
            CopySource=copy_source,
            Bucket=bucket_name,
            Key=destination_key
        )

        # Delete the original object
        r2_client.delete_object(Bucket=bucket_name, Key=source_key)

        logger.info(f"Successfully moved R2 object from {source_key} to {destination_key}")
        return True
    except Exception as e:
        logger.error(f"Failed to move R2 object from {source_key} to {destination_key}: {str(e)}")
        return False


def copy_r2_object(source_key, destination_key):
    """
    Copy an object to a new location in R2

    Args:
        source_key: Source object key
        destination_key: Destination object key

    Returns:
        True if successful, False otherwise
    """
    try:
        r2_client = get_r2_client()
        bucket_name = current_app.config.get('R2_BUCKET_NAME')

        # Copy the object
        copy_source = {'Bucket': bucket_name, 'Key': source_key}
        r2_client.copy_object(
            CopySource=copy_source,
            Bucket=bucket_name,
            Key=destination_key
        )

        logger.info(f"Successfully copied R2 object from {source_key} to {destination_key}")
        return True
    except Exception as e:
        logger.error(f"Failed to copy R2 object from {source_key} to {destination_key}: {str(e)}")
        return False


def generate_pending_path(original_path):
    """
    Generate pending content path from original path

    Original: beps-contents/{channel}/{category}/{page}.png
    Pending:  beps-content-archive/pending/{channel}/{category}/{page}.png

    Args:
        original_path: Original R2 object key

    Returns:
        Pending path
    """
    # Replace the base prefix
    if original_path.startswith('beps-contents/'):
        return original_path.replace('beps-contents/', 'beps-archive/pending/', 1)
    else:
        # Fallback: add pending prefix
        return f'beps-archive/pending/{original_path}'


def generate_archived_path(original_path, timestamp_suffix):
    """
    Generate archived content path from original path

    Original: beps-contents/{channel}/{category}/{page}.png
    Archived: beps-archive/old/{channel}/{category}/{page}__{timestamp}.png

    Args:
        original_path: Original R2 object key
        timestamp_suffix: Timestamp suffix (yyyymmddHHMM format)

    Returns:
        Archived path with timestamp
    """
    import os as os_module

    # Extract directory and filename
    dirname = os_module.path.dirname(original_path)
    filename = os_module.path.basename(original_path)

    # Split filename and extension
    name, ext = os_module.path.splitext(filename)

    # Generate archived filename with timestamp
    archived_filename = f"{name}__{timestamp_suffix}{ext}"

    # Replace base prefix and reconstruct path
    if dirname.startswith('beps-contents/'):
        archived_dirname = dirname.replace('beps-contents/', 'beps-archive/old/', 1)
    else:
        archived_dirname = f'beps-archive/old/{dirname}'

    return f"{archived_dirname}/{archived_filename}"


def get_r2_object_metadata(object_key):
    """
    Get metadata for an R2 object

    Args:
        object_key: The R2 object key

    Returns:
        Dictionary with metadata (size, last_modified, etc.) or None if not found
    """
    try:
        r2_client = get_r2_client()
        bucket_name = current_app.config.get('R2_BUCKET_NAME')

        response = r2_client.head_object(Bucket=bucket_name, Key=object_key)

        return {
            'size': response.get('ContentLength', 0),
            'last_modified': response.get('LastModified'),
            'content_type': response.get('ContentType'),
            'etag': response.get('ETag')
        }
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return None
        else:
            logger.error(f"Error getting R2 object metadata: {str(e)}")
            raise
    except Exception as e:
        logger.error(f"Failed to get R2 object metadata: {str(e)}")
        raise


def list_r2_objects(prefix):
    """
    List objects in R2 with given prefix

    Args:
        prefix: Prefix to filter objects

    Returns:
        List of object keys
    """
    try:
        r2_client = get_r2_client()
        bucket_name = current_app.config.get('R2_BUCKET_NAME')

        response = r2_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix
        )

        if 'Contents' in response:
            return [obj['Key'] for obj in response['Contents']]
        else:
            return []

    except Exception as e:
        logger.error(f"Failed to list R2 objects with prefix {prefix}: {str(e)}")
        return []


def rename_hierarchy_r2_objects(old_name, new_name, hierarchy_type='channel', parent_path=''):
    """
    Rename R2 objects when hierarchy changes (channel/folder/page rename)

    This function finds all R2 objects matching the old hierarchy path and renames them
    to match the new hierarchy path. It handles:
    - Main content files
    - Pending content (beps-archive/pending/)
    - Archived content (beps-archive/old/)

    Args:
        old_name: Old name of the channel/folder/page
        new_name: New name of the channel/folder/page
        hierarchy_type: Type of hierarchy ('channel', 'folder', 'page')
        parent_path: Parent path in the hierarchy (e.g., "Channel1/Folder1")

    Returns:
        Dictionary with success status and details
    """
    try:
        r2_client = get_r2_client()
        bucket_name = current_app.config.get('R2_BUCKET_NAME')

        # Sanitize names for R2 paths
        old_safe_name = old_name.replace('/', '⁄').replace('\\', '⁄')
        new_safe_name = new_name.replace('/', '⁄').replace('\\', '⁄')

        # Build the old and new path prefixes
        if parent_path:
            parent_safe = parent_path.replace('/', '⁄').replace('\\', '⁄')
            old_prefix = f"{parent_safe}/{old_safe_name}"
            new_prefix = f"{parent_safe}/{new_safe_name}"
        else:
            old_prefix = old_safe_name
            new_prefix = new_safe_name

        # Prefixes to check in R2
        prefixes_to_check = [
            f"beps-contents/{old_prefix}",
            f"beps-archive/pending/{old_prefix}",
            f"beps-archive/old/{old_prefix}"
        ]

        renamed_count = 0
        errors = []

        for prefix in prefixes_to_check:
            # List all objects with this prefix
            objects = list_r2_objects(prefix)

            for old_key in objects:
                # Generate new key by replacing the old prefix
                if hierarchy_type == 'channel':
                    # Replace the channel name (first component after base prefix)
                    new_key = old_key.replace(f"/{old_safe_name}/", f"/{new_safe_name}/", 1)
                elif hierarchy_type == 'folder':
                    # Replace the folder name in the path
                    new_key = old_key.replace(f"/{old_safe_name}/", f"/{new_safe_name}/", 1)
                elif hierarchy_type == 'page':
                    # For pages, we need to rename both the file and the folder (for additionals)
                    import os as os_module

                    # Get the file extension from the old key
                    old_basename = os_module.basename(old_key)
                    old_name_without_ext = os_module.path.splitext(old_name)[0]
                    new_name_without_ext = os_module.path.splitext(new_name)[0]

                    # Replace in path (for additional content folders)
                    new_key = old_key.replace(f"/{old_safe_name}/", f"/{new_safe_name}/")

                    # Also replace the filename itself if it matches
                    if old_basename.startswith(old_name):
                        new_basename = old_basename.replace(old_name, new_name, 1)
                        new_key = os_module.path.join(os_module.path.dirname(new_key), new_basename)

                # Move the object
                try:
                    if move_r2_object(old_key, new_key):
                        renamed_count += 1
                        logger.info(f"Renamed R2 object: {old_key} -> {new_key}")
                    else:
                        errors.append(f"Failed to move {old_key} to {new_key}")
                except Exception as e:
                    error_msg = f"Error moving {old_key}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)

        return {
            'success': len(errors) == 0,
            'renamed_count': renamed_count,
            'errors': errors
        }

    except Exception as e:
        logger.error(f"Failed to rename hierarchy R2 objects: {str(e)}")
        return {
            'success': False,
            'renamed_count': 0,
            'errors': [str(e)]
        } 