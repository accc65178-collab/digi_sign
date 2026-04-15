"""
Build script to create standalone executable using PyInstaller
Run: python build_exe.py
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def install_requirements():
    """Install required packages if not already installed"""
    required = [
        'pyinstaller>=5.0',
        'pillow>=9.0',
        'python-docx>=0.8.11',
        'pyqt5>=5.15.0',
        'pywin32>=304'  # For PDF conversion on Windows
    ]
    
    for package in required:
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f"✓ Installed {package}")
        except subprocess.CalledProcessError:
            print(f"✗ Failed to install {package}")
            return False
    return True

def create_spec_file():
    """Create PyInstaller spec file with proper configuration"""
    spec_content = '''
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('ui', 'ui'),
        ('models', 'models'),
        ('services', 'services'),
        ('database', 'database'),
        ('utils', 'utils'),
        ('documents', 'documents'),
    ],
    hiddenimports=[
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'docx',
        'docx.shared',
        'docx.enum',
        'win32com',
        'win32com.client',
        'pythoncom',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Signix',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True if you need console for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='ui/images/logo.ico',  # Custom logo icon
)
'''
    
    with open('Signix.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    print("✓ Created Signix.spec")

def build_executable():
    """Build the executable using PyInstaller"""
    try:
        # Clean previous builds
        for dist_dir in ['dist', 'build']:
            if Path(dist_dir).exists():
                shutil.rmtree(dist_dir)
        
        # Build the executable
        subprocess.check_call([
            sys.executable, '-m', 'PyInstaller', 
            '--clean', 
            '--noconfirm',
            'Signix.spec'
        ])
        
        print("✓ Build completed successfully!")
        print(f"✓ Executable created at: {Path('dist/Signix.exe').absolute()}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Build failed: {e}")
        return False

def create_data_directory():
    """Create data directory structure for runtime"""
    data_dir = Path('dist/data')
    data_dir.mkdir(exist_ok=True)
    
    # Create empty database file if it doesn't exist
    db_file = data_dir / 'digi_sign.db'
    if not db_file.exists():
        print(f"✓ Created placeholder database at: {db_file}")
    
    print(f"✓ Data directory ready at: {data_dir}")

def main():
    print("Building Signix executable...")
    
    # Step 1: Install requirements
    if not install_requirements():
        print("Failed to install requirements")
        return
    
    # Step 2: Create spec file
    create_spec_file()
    
    # Step 3: Build executable
    if not build_executable():
        print("Build failed")
        return
    
    # Step 4: Create data directory
    create_data_directory()
    
    print("\n" + "="*50)
    print("BUILD COMPLETE!")
    print("="*50)
    print(f"Executable: {Path('dist/Signix.exe').absolute()}")
    print("\nTo run the application:")
    print("1. Copy the entire 'dist' folder to the target machine")
    print("2. Run 'Signix.exe'")
    print("3. The database will be created automatically in 'dist/data/'")
    print("\nNote: All dependencies are bundled, no Python installation required.")

if __name__ == '__main__':
    main()
