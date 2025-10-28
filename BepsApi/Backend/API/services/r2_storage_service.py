"""
R2 Storage Service

Handles all R2/Cloudflare storage operations including:
- File existence checking
- Path generation
- Upload/download operations
"""

import logging
import datetime
from typing import Optional, Dict, Any

# Cache for R2 existence checks to improve performance
_r2_existence_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


class R2StorageService:
    """Service for handling R2 storage operations"""
    
    @staticmethod
    def check_page_detail_content_exists(detail_id: int, detail_name: str = None, 
                                       detail_object_id: str = None, 
                                       updated_at: datetime.datetime = None,
                                       use_cache: bool = True) -> bool:
        """
        Check if a page detail's content actually exists in R2 storage by deriving path from node structure
        
        Args:
            detail_id: ID of the page detail
            detail_name: Name of the detail (for path generation)
            detail_object_id: Object ID from database (legacy, not used for existence check)
            updated_at: Last update timestamp (for cache invalidation)
            use_cache: Whether to use caching
            
        Returns:
            True if file exists in R2, False otherwise
        """
        # Generate cache key
        cache_key = f"page_detail_{detail_id}_{updated_at.timestamp() if updated_at else 0}"
        
        # Check cache first
        if use_cache and cache_key in _r2_existence_cache:
            cache_entry = _r2_existence_cache[cache_key]
            # Check if cache entry is still valid
            if (datetime.datetime.now() - cache_entry['timestamp']).seconds < CACHE_TTL_SECONDS:
                return cache_entry['exists']
        
        try:
            # Import here to avoid circular imports
            from blueprints.contents.r2_utils import check_r2_object_exists, generate_r2_object_key
            
            # Always derive R2 path from node structure (same approach as other endpoints)
            detail_name_clean = detail_name or f"detail_{detail_id}"
            detail_extensions = ['.pdf', '.webm', '.mp4', '.avi', '.mov', '.wmv', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.png', '.jpg', '.jpeg', '.gif', '.webp']
            
            result = False
            
            # Try multiple extensions to find the actual file
            for ext in detail_extensions:
                test_filename = f"{detail_name_clean}{ext}"
                test_object_key = generate_r2_object_key(detail_id, test_filename, is_page_detail=True)
                
                if check_r2_object_exists(test_object_key):
                    result = True
                    break
            
            # Cache the result
            if use_cache:
                _r2_existence_cache[cache_key] = {
                    'exists': result,
                    'timestamp': datetime.datetime.now()
                }
                
                # Simple cache cleanup
                R2StorageService._cleanup_cache()
            
            return result
            
        except ValueError as e:
            # This is likely a credentials error
            if "Missing required R2 credentials" in str(e):
                logging.warning(f"🔑 R2 credentials not configured, making intelligent guess for page detail {detail_id}")
                # When R2 is not available, make intelligent guess based on name pattern
                name_suggests_content = bool(
                    detail_name and 
                    (any(detail_name.lower().endswith(ext.lower()) for ext in ['.pdf', '.webm', '.mp4', '.avi', '.mov', '.wmv', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.png', '.jpg', '.jpeg', '.gif', '.webp']) or 
                     any(char.isdigit() for char in detail_name) or  # Has numbers
                     len(detail_name) > 3)  # Not just placeholder names
                )
                
                fallback_result = name_suggests_content
                
                # Cache the fallback result too
                if use_cache:
                    _r2_existence_cache[cache_key] = {
                        'exists': fallback_result,
                        'timestamp': datetime.datetime.now()
                    }
                
                return fallback_result
            else:
                raise
        except Exception as e:
            logging.error(f"Error checking R2 content for page detail {detail_id}: {str(e)}")
            # Fallback to intelligent guess based on name
            if detail_name:
                return any(detail_name.lower().endswith(ext.lower()) for ext in ['.pdf', '.webm', '.mp4', '.avi', '.mov', '.wmv', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.png', '.jpg', '.jpeg', '.gif', '.webp'])
            return False
    
    @staticmethod
    def check_page_content_exists(page_id: int, page_name: str = None, 
                                page_object_id: str = None,
                                updated_at: datetime.datetime = None,
                                use_cache: bool = True) -> bool:
        """
        Check if a page's content actually exists in R2 storage by deriving path from node structure
        
        Args:
            page_id: ID of the page
            page_name: Name of the page (for path generation)
            page_object_id: Object ID from database (legacy, not used for existence check)
            updated_at: Last update timestamp (for cache invalidation)
            use_cache: Whether to use caching
            
        Returns:
            True if file exists in R2, False otherwise
        """
        # Generate cache key
        cache_key = f"page_{page_id}_{updated_at.timestamp() if updated_at else 0}"
        
        # Check cache first
        if use_cache and cache_key in _r2_existence_cache:
            cache_entry = _r2_existence_cache[cache_key]
            # Check if cache entry is still valid
            if (datetime.datetime.now() - cache_entry['timestamp']).seconds < CACHE_TTL_SECONDS:
                return cache_entry['exists']
        
        try:
            # Import here to avoid circular imports
            from blueprints.contents.r2_utils import check_r2_object_exists, generate_r2_object_key
            from models import ContentRelPageDetails
            
            # Always derive R2 path from node structure (same approach as r2-image-url endpoint)
            page_name_clean = page_name or f"file_{page_id}"
            image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf']
            
            result = False
            
            # 1. Try multiple extensions to find the main page file
            for ext in image_extensions:
                test_filename = f"{page_name_clean}{ext}"
                test_object_key = generate_r2_object_key(page_id, test_filename, is_page_detail=False)
                
                if check_r2_object_exists(test_object_key):
                    result = True
                    break
            
            # 2. If no main file found, check for page detail files
            if not result:
                page_details = ContentRelPageDetails.query.filter_by(
                    page_id=page_id,
                    is_deleted=False
                ).all()
                
                for detail in page_details:
                    detail_extensions = ['.pdf', '.webm', '.mp4', '.avi', '.mov', '.wmv', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx']
                    for ext in detail_extensions:
                        detail_filename = f"{detail.name}{ext}"
                        detail_object_key = generate_r2_object_key(detail.id, detail_filename, is_page_detail=True)
                        
                        if check_r2_object_exists(detail_object_key):
                            result = True
                            break
                    
                    if result:
                        break
            
            # Cache the result
            if use_cache:
                _r2_existence_cache[cache_key] = {
                    'exists': result,
                    'timestamp': datetime.datetime.now()
                }
                
                # Simple cache cleanup
                R2StorageService._cleanup_cache()
            
            return result
            
        except ValueError as e:
            # This is likely a credentials error
            if "Missing required R2 credentials" in str(e):
                logging.warning(f"🔑 R2 credentials not configured, making intelligent guess for page {page_id}")
                # When R2 is not available, make intelligent guess based on name pattern and page details
                name_suggests_content = bool(
                    page_name and 
                    (any(page_name.lower().endswith(ext.lower()) for ext in ['.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp']) or 
                     any(char.isdigit() for char in page_name) or  # Has numbers (like 002_08.pdf)
                     len(page_name) > 3)  # Not just placeholder names
                )
                
                # Also check if page has detail files
                has_page_details = False
                try:
                    from models import ContentRelPageDetails
                    has_page_details = ContentRelPageDetails.query.filter_by(
                        page_id=page_id,
                        is_deleted=False
                    ).count() > 0
                except Exception:
                    pass
                
                fallback_result = name_suggests_content or has_page_details
                
                # Cache the fallback result too
                if use_cache:
                    _r2_existence_cache[cache_key] = {
                        'exists': fallback_result,
                        'timestamp': datetime.datetime.now()
                    }
                
                return fallback_result
            else:
                raise
        except Exception as e:
            logging.error(f"❌ Error checking R2 content for page {page_id}: {str(e)}", exc_info=True)
            # Fallback to intelligent guess based on name
            if page_name:
                return any(page_name.lower().endswith(ext.lower()) for ext in ['.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp'])
            return False
    
    @staticmethod
    def _cleanup_cache():
        """Clean up old cache entries to prevent memory bloat"""
        if len(_r2_existence_cache) > 1000:
            # Remove entries older than TTL
            now = datetime.datetime.now()
            keys_to_remove = []
            
            for key, entry in _r2_existence_cache.items():
                if (now - entry['timestamp']).seconds > CACHE_TTL_SECONDS:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del _r2_existence_cache[key]
            
            # If still too many, remove oldest entries
            if len(_r2_existence_cache) > 800:
                oldest_keys = sorted(_r2_existence_cache.keys(), 
                                   key=lambda k: _r2_existence_cache[k]['timestamp'])[:200]
                for key in oldest_keys:
                    del _r2_existence_cache[key]
    
    @staticmethod
    def clear_cache():
        """Clear all cached R2 existence checks"""
        global _r2_existence_cache
        _r2_existence_cache.clear() 