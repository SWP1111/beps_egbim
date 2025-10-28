#!/usr/bin/env python3
"""
Apply database migration for content manager refactoring
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

try:
    import psycopg2
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    # Database connection from .env
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@127.0.0.1:5432/beps')

    print(f"Connecting to database: {DATABASE_URL.split('@')[1]}")  # Hide password

    # Connect to database
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cursor = conn.cursor()

    # Read migration file
    migration_file = '../DB/migrations/001_content_manager_refactor.sql'
    print(f"Reading migration file: {migration_file}")

    with open(migration_file, 'r', encoding='utf-8') as f:
        migration_sql = f.read()

    print("Applying migration...")

    # Execute migration
    cursor.execute(migration_sql)

    print("✅ Migration applied successfully!")

    # Verify tables exist
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name IN ('page_additionals', 'pending_content', 'archived_content')
        ORDER BY table_name
    """)

    tables = cursor.fetchall()
    print("\nVerifying tables:")
    for table in tables:
        print(f"  ✅ {table[0]}")

    if len(tables) == 3:
        print("\n✅ All tables created successfully!")
    else:
        print(f"\n⚠️  Warning: Expected 3 tables, found {len(tables)}")

    cursor.close()
    conn.close()

except ImportError as e:
    print(f"❌ Error: Required module not found: {e}")
    print("\nPlease install required packages:")
    print("  pip install psycopg2-binary python-dotenv")
    sys.exit(1)

except Exception as e:
    print(f"❌ Error applying migration: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
