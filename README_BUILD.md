# Build DigiSign Executable

## Quick Build

```bash
python build_exe.py
```

This will:
1. Install all required dependencies
2. Create PyInstaller configuration
3. Build standalone executable
4. Prepare data directories

## Manual Build Steps

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Build Executable
```bash
pyinstaller --clean --noconfirm DigiSign.spec
```

### 3. Distribution
- The executable will be in `dist/DigiSign.exe`
- Copy the entire `dist` folder to target machines
- Database will be created automatically at runtime

## What Gets Included

✅ **All Python modules**: ui, models, services, database, utils  
✅ **All dependencies**: PyQt5, Pillow, python-docx, pywin32  
✅ **Database creation**: Automatic on first run  
✅ **Reference documents**: Bundled from `reference_docs/`  
✅ **Barcode/QR functionality**: Fully included  

## Runtime Requirements

Target machine needs:
- Windows 10 or later
- No Python installation required
- Microsoft Word (for PDF export functionality)

## Database & Data Storage

- Database: `dist/data/digi_sign.db` (created automatically)
- User signatures: Stored in database
- Documents: Saved in user-selected locations

## Troubleshooting

**If executable fails to start:**
1. Run with `--console` flag in spec to see errors
2. Check Windows Event Viewer for detailed error messages
3. Ensure all Visual C++ Redistributables are installed

**If PDF export doesn't work:**
- Microsoft Word must be installed on target machine
- pywin32 handles the COM interface automatically

**File size optimization:**
- Current build includes all PyQt5 modules (~50MB)
- Can be reduced by excluding unused PyQt5 modules in spec file
# If you need to reset the database again
  python reset_database.py