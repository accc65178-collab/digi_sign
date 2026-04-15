"""
Reset database to clean state with only admin user
Run: python reset_database.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[0]
sys.path.insert(0, str(project_root))

from database.db_manager import DbManager, DbConfig
from models.user import User
import hashlib

def create_admin_password_hash(password: str) -> str:
    """Create bcrypt hash for admin password"""
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    except ImportError:
        raise RuntimeError("bcrypt is required. Install with: pip install bcrypt")

def get_database_path() -> Path:
    """Get persistent database path for the application"""
    # Check if running from exe
    if getattr(sys, 'frozen', False):
        # Running from exe - use data folder within the exe directory for shared network access
        exe_dir = Path(sys.executable).parent
        db_dir = exe_dir / "data"
        db_dir.mkdir(parents=True, exist_ok=True)
        return db_dir / "app.db"
    else:
        # Running from source - use local documents folder
        return project_root / "documents" / "app.db"


def reset_database():
    """Reset database to clean state with only admin user"""
    
    # Database path (works for both source and exe)
    db_path = get_database_path()
    
    # Remove existing database if it exists
    if db_path.exists():
        print(f"Removing existing database: {db_path}")
        db_path.unlink()
    
    # Create new database manager
    config = DbConfig(db_path=db_path)
    db_manager = DbManager(config)
    
    print("Creating fresh database...")
    
    # Initialize database tables
    db_manager.init_db()
    print("✓ Database tables created")
    
    # Create admin user
    admin_password = "admin@123"
    admin_hash = create_admin_password_hash(admin_password)
    
    # Insert admin user using individual parameters
    admin_id = db_manager.create_user(
        name="admin",
        full_name="Administrator",
        employee_id="ADMIN001",
        department="IT",
        lab="Main",
        username="admin",
        password_hash=admin_hash,
        designation="System Administrator",
        role="Admin",  # Changed to "Admin" (capital A) to match dashboard check
        status="Approved",  # Changed from "active" to "Approved"
        enabled=1
    )
    
    print("✓ Database reset complete!")
    print("✓ Admin user created:")
    print("  Username: admin")
    print("  Password: admin@123")
    print("  Employee ID: ADMIN001")
    print(f"✓ Database location: {db_path}")
    
    # Verify admin user
    verify_admin = db_manager.get_user_by_username("admin")
    if verify_admin:
        print("✓ Admin user verification successful")
    else:
        print("✗ Admin user verification failed")

if __name__ == "__main__":
    try:
        reset_database()
        print("\n" + "="*50)
        print("DATABASE RESET COMPLETE")
        print("="*50)
        print("You can now start the application with:")
        print("python main.py")
        print("\nLogin credentials:")
        print("Username: admin")
        print("Password: admin@123")
    except Exception as e:
        print(f"Error resetting database: {e}")
        sys.exit(1)
