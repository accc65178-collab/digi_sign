"""
Reset database for EXE version (shared on network)
Run this script to reset the shared database when running from the executable
This will reset the database in the dist/data folder (shared by all users)
"""

import os
import sys
from pathlib import Path
import bcrypt

def get_exe_database_path() -> Path:
    """Get database path for EXE version (shared on network)"""
    # For shared network access, use the data folder within the exe directory
    exe_path = Path(__file__).resolve().parent / "dist" / "DigiSign.exe"
    if exe_path.exists():
        exe_dir = exe_path.parent
    else:
        # Fallback: assume script is in the dist folder
        exe_dir = Path(__file__).resolve().parent
    
    db_dir = exe_dir / "data"
    return db_dir / "app.db"

def reset_exe_database():
    """Reset database for EXE version"""
    
    # Database path for EXE
    db_path = get_exe_database_path()
    
    print(f"EXE Database location: {db_path}")
    
    # Remove existing database if it exists
    if db_path.exists():
        print(f"Removing existing database: {db_path}")
        db_path.unlink()
    else:
        print("No existing database found")
    
    # Create directory if it doesn't exist
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    print("✓ EXE database will be created automatically when you run DigiSign.exe")
    print("✓ Admin login credentials:")
    print("  Username: admin")
    print("  Password: admin@123")
    print(f"✓ Database location: {db_path}")

if __name__ == "__main__":
    try:
        reset_exe_database()
        print("\n" + "="*50)
        print("EXE DATABASE RESET COMPLETE")
        print("="*50)
        print("Now run DigiSign.exe to create a fresh database")
    except Exception as e:
        print(f"Error: {e}")
        input("Press Enter to exit...")
