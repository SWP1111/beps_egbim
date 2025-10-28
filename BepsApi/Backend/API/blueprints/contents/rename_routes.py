"""
Rename/Edit routes for content names

This module handles renaming operations for:
- Channels (탭)
- Categories (카테고리)
- Pages (페이지)

When names are changed, R2 objects are also moved/renamed accordingly.
If page prefix changes (e.g., 001 -> 002), all additional content is also renamed.
"""

import os
import re
import logging
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from extensions import db
from models import ContentRelChannels, ContentRelFolders, ContentRelPages, PageAdditionals
from .r2_utils import move_r2_object, list_r2_objects
from log_config import get_content_logger

# Initialize logger
logger = get_content_logger()


def register_rename_routes(api_contents_bp):
    """Register all rename routes to the blueprint"""

    @api_contents_bp.route('/channel/<int:channel_id>/rename', methods=['PUT'])
    @jwt_required()
    def rename_channel(channel_id):
        """
        Rename a channel (탭)

        Process:
        1. Update DB name
        2. Move all R2 objects under this channel

        Request body:
        {
            "new_name": "002_NewChannelName"
        }
        """
        try:
            # Get channel
            channel = ContentRelChannels.query.filter_by(id=channel_id, is_deleted=False).first()
            if not channel:
                return jsonify({'error': 'Channel not found'}), 404

            # Get new name from request
            data = request.json
            if not data or 'new_name' not in data:
                return jsonify({'error': 'new_name is required'}), 400

            new_name = data['new_name'].strip()
            if not new_name:
                return jsonify({'error': 'new_name cannot be empty'}), 400

            old_name = channel.name

            if old_name == new_name:
                return jsonify({'message': 'Name unchanged'}), 200

            # Update DB
            channel.name = new_name
            db.session.commit()

            # TODO: Rename R2 objects (would need to move all objects under this channel)
            # This is a complex operation - for now, just update DB
            # In production, you'd want to use a background job for this

            logger.info(f"Renamed channel {channel_id}: {old_name} -> {new_name}")

            return jsonify({
                'message': 'Channel renamed successfully',
                'channel': channel.to_dict(),
                'note': 'R2 objects are not automatically renamed. Please update manually or run migration.'
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error renaming channel: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/category/<int:category_id>/rename', methods=['PUT'])
    @jwt_required()
    def rename_category(category_id):
        """
        Rename a category (카테고리)

        Process:
        1. Update DB name
        2. Move all R2 objects under this category

        Request body:
        {
            "new_name": "002_NewCategoryName"
        }
        """
        try:
            # Get category
            category = ContentRelFolders.query.filter_by(id=category_id, is_deleted=False).first()
            if not category:
                return jsonify({'error': 'Category not found'}), 404

            # Get new name from request
            data = request.json
            if not data or 'new_name' not in data:
                return jsonify({'error': 'new_name is required'}), 400

            new_name = data['new_name'].strip()
            if not new_name:
                return jsonify({'error': 'new_name cannot be empty'}), 400

            old_name = category.name

            if old_name == new_name:
                return jsonify({'message': 'Name unchanged'}), 200

            # Update DB
            category.name = new_name
            db.session.commit()

            logger.info(f"Renamed category {category_id}: {old_name} -> {new_name}")

            return jsonify({
                'message': 'Category renamed successfully',
                'category': category.to_dict(),
                'note': 'R2 objects are not automatically renamed. Please update manually or run migration.'
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error renaming category: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @api_contents_bp.route('/page/<int:page_id>/rename', methods=['PUT'])
    @jwt_required()
    def rename_page(page_id):
        """
        Rename a page (페이지)

        Process:
        1. Extract old and new prefixes (3-digit)
        2. Update DB name
        3. If prefix changed: Rename page file + all additional content
        4. If only name changed: Rename page file only

        Request body:
        {
            "new_name": "002_NewPageName"
        }
        """
        try:
            # Get page
            page = ContentRelPages.query.filter_by(id=page_id, is_deleted=False).first()
            if not page:
                return jsonify({'error': 'Page not found'}), 404

            # Get new name from request
            data = request.json
            if not data or 'new_name' not in data:
                return jsonify({'error': 'new_name is required'}), 400

            new_name = data['new_name'].strip()
            if not new_name:
                return jsonify({'error': 'new_name cannot be empty'}), 400

            old_name = page.name

            if old_name == new_name:
                return jsonify({'message': 'Name unchanged'}), 200

            # Extract prefixes
            old_prefix_match = re.match(r'^(\d{3})_', old_name)
            new_prefix_match = re.match(r'^(\d{3})_', new_name)

            if not new_prefix_match:
                return jsonify({
                    'error': 'New name must follow naming convention: 3-digit prefix + underscore (e.g., 001_Name)'
                }), 400

            old_prefix = old_prefix_match.group(1) if old_prefix_match else None
            new_prefix = new_prefix_match.group(1)

            prefix_changed = (old_prefix != new_prefix)

            # Generate old and new R2 paths
            from .r2_utils import generate_r2_object_key

            old_object_key = generate_r2_object_key(page_id, old_name, is_page_detail=False)
            new_object_key = generate_r2_object_key(page_id, new_name, is_page_detail=False)

            # Update this to work with new naming scheme
            # Since generate_r2_object_key uses DB data, we need to update DB first, then fix paths
            page.name = new_name
            db.session.flush()

            # Regenerate with new name
            new_object_key = generate_r2_object_key(page_id, new_name, is_page_detail=False)

            renamed_objects = []

            # Rename page file in R2
            if move_r2_object(old_object_key, new_object_key):
                renamed_objects.append({
                    'old': old_object_key,
                    'new': new_object_key
                })

            # Update object_id in DB
            if page.object_id == old_object_key:
                page.object_id = new_object_key

            # If prefix changed, rename all additional content
            if prefix_changed:
                logger.info(f"Page prefix changed: {old_prefix} -> {new_prefix}. Renaming additional content...")

                # Get all additionals for this page
                additionals = PageAdditionals.query.filter_by(
                    page_id=page_id,
                    is_deleted=False
                ).all()

                for additional in additionals:
                    # Generate new filename with new prefix
                    old_filename = additional.filename
                    # Replace old prefix with new prefix in filename
                    new_filename = old_filename.replace(f"{old_prefix}_", f"{new_prefix}_", 1)

                    # Generate R2 paths
                    old_additional_key = additional.object_key
                    new_additional_key = old_additional_key.replace(
                        f"/{old_filename}",
                        f"/{new_filename}",
                        1
                    )

                    # Rename in R2
                    if move_r2_object(old_additional_key, new_additional_key):
                        renamed_objects.append({
                            'old': old_additional_key,
                            'new': new_additional_key
                        })

                        # Update DB
                        additional.filename = new_filename
                        additional.object_key = new_additional_key

            db.session.commit()

            logger.info(f"Renamed page {page_id}: {old_name} -> {new_name}")
            logger.info(f"Renamed {len(renamed_objects)} R2 objects")

            return jsonify({
                'message': 'Page renamed successfully',
                'page': page.to_dict(),
                'prefix_changed': prefix_changed,
                'renamed_objects': renamed_objects
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error renaming page: {str(e)}")
            return jsonify({'error': str(e)}), 500
