#!/usr/bin/env python3
"""
Test script to verify imports are working properly
"""
import sys
print("Python Path:")
print(sys.path)

try:
    import extensions
    print("✅ Successfully imported extensions")
except ImportError as e:
    print("❌ Failed to import extensions:", str(e))

try:
    from extensions import db
    print("✅ Successfully imported db from extensions")
except ImportError as e:
    print("❌ Failed to import db from extensions:", str(e))

try:
    import sqlalchemy
    print("✅ Successfully imported sqlalchemy")
except ImportError as e:
    print("❌ Failed to import sqlalchemy:", str(e))

try:
    from sqlalchemy.sql import union_all
    print("✅ Successfully imported union_all from sqlalchemy.sql")
except ImportError as e:
    print("❌ Failed to import union_all from sqlalchemy.sql:", str(e))

try:
    from sqlalchemy.orm import aliased
    print("✅ Successfully imported aliased from sqlalchemy.orm")
except ImportError as e:
    print("❌ Failed to import aliased from sqlalchemy.orm:", str(e))

try:
    import models
    print("✅ Successfully imported models")
except ImportError as e:
    print("❌ Failed to import models:", str(e))

# Print current directory
import os
print("Current directory:", os.getcwd()) 