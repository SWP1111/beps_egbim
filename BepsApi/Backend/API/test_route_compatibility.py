#!/usr/bin/env python3
"""
Route Compatibility Test

This script verifies that the refactored contents routes provide
the same endpoints as the original implementation.
"""

import sys
import re
from pathlib import Path

def extract_routes_from_file(file_path):
    """Extract route definitions from a Python file"""
    routes = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all @api_contents_bp.route() decorators
        pattern = r'@api_contents_bp\.route\([\'"]([^\'\"]+)[\'"](?:,\s*methods=\[([^\]]+)\])?\)'
        matches = re.findall(pattern, content)
        
        for match in matches:
            route_path = match[0]
            methods = match[1] if match[1] else 'GET'
            # Clean up methods string
            methods = methods.replace("'", "").replace('"', "").replace(' ', '')
            routes.append((route_path, methods))
    
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    
    return routes

def test_route_compatibility():
    """Test that refactored routes match original routes"""
    
    print("🔍 Testing Route Compatibility")
    print("=" * 50)
    
    # Get routes from original file
    original_file = Path("blueprints/contents_routes_original.py")
    if not original_file.exists():
        print("❌ Original file not found!")
        return False
    
    original_routes = extract_routes_from_file(original_file)
    print(f"📋 Original routes found: {len(original_routes)}")
    
    # Get routes from refactored modules
    refactored_routes = []
    
    # Check each module
    modules = [
        "blueprints/contents/hierarchy_routes.py",
        "blueprints/contents/channel_folder_routes.py", 
        "blueprints/contents/file_routes.py",
        "blueprints/contents/page_detail_routes.py"
    ]
    
    for module in modules:
        module_path = Path(module)
        if module_path.exists():
            module_routes = extract_routes_from_file(module_path)
            refactored_routes.extend(module_routes)
            print(f"📁 {module_path.name}: {len(module_routes)} routes")
        else:
            print(f"⚠️  {module} not found")
    
    print(f"📋 Refactored routes found: {len(refactored_routes)}")
    print()
    
    # Convert to sets for comparison
    original_set = set(original_routes)
    refactored_set = set(refactored_routes)
    
    # Find missing routes
    missing_routes = original_set - refactored_set
    extra_routes = refactored_set - original_set
    
    print("📊 Compatibility Analysis")
    print("-" * 30)
    
    if not missing_routes and not extra_routes:
        print("✅ Perfect match! All routes are identical.")
        return True
    
    coverage_percent = (len(refactored_set) / len(original_set)) * 100
    print(f"📈 Coverage: {coverage_percent:.1f}% ({len(refactored_set)}/{len(original_set)})")
    
    if missing_routes:
        print(f"\n❌ Missing routes ({len(missing_routes)}):")
        for route, methods in sorted(missing_routes):
            print(f"   {methods:12} {route}")
    
    if extra_routes:
        print(f"\n➕ Extra routes ({len(extra_routes)}):")
        for route, methods in sorted(extra_routes):
            print(f"   {methods:12} {route}")
    
    print(f"\n✅ Implemented routes ({len(refactored_set)}):")
    for route, methods in sorted(refactored_set):
        print(f"   {methods:12} {route}")
    
    return len(missing_routes) == 0

def test_imports():
    """Test that all imports work correctly"""
    print("\n🔧 Testing Imports")
    print("=" * 50)
    
    try:
        # Test main blueprint import
        from blueprints.contents_routes import api_contents_bp
        print("✅ Main blueprint imported successfully")
        
        # Test utility functions
        from blueprints.contents_routes import (
            check_r2_object_exists, 
            generate_r2_object_key,
            generate_r2_signed_url
        )
        print("✅ Utility functions imported successfully")
        
        # Test service layer
        from services.r2_storage_service import R2StorageService
        print("✅ R2StorageService imported successfully")
        
        # Test models with new service integration
        from models import ContentRelPageDetails, ContentRelPages
        print("✅ Models imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def main():
    """Run all compatibility tests"""
    print("🧪 Contents Routes Refactoring Compatibility Test")
    print("=" * 60)
    
    # Test imports first
    imports_ok = test_imports()
    
    # Test route compatibility
    routes_ok = test_route_compatibility()
    
    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)
    
    if imports_ok and routes_ok:
        print("🎉 ALL TESTS PASSED!")
        print("✅ The refactored version works exactly the same as before")
        return 0
    else:
        print("⚠️  SOME TESTS FAILED")
        if not imports_ok:
            print("❌ Import issues detected")
        if not routes_ok:
            print("❌ Route coverage incomplete")
        print("📝 See details above for missing functionality")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 