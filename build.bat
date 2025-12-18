@echo off
rem This batch file builds the Network Drive Manager application into a single executable.
rem It uses PyInstaller. Make sure you have it installed: pip install pyinstaller

echo ===================================
echo  Building Network Drive Manager EXE
echo ===================================
echo.

rem Check if icon.ico exists
if not exist "icon.ico" (
    echo WARNING: icon.ico not found. The executable will not have a custom icon.
    echo Please create a 256x256 .ico file named icon.ico in this directory.
    echo.
)

rem Run PyInstaller
echo Running PyInstaller...
pyinstaller --onefile --windowed --icon="icon.ico" --add-data="icon.ico;." --name "NetworkDrive" NetworkDrive.py

rem Check if PyInstaller succeeded
if %errorlevel% neq 0 (
    echo.
    echo **********************************
    echo  PyInstaller FAILED with errors.
    echo **********************************
    pause
    exit /b %errorlevel%
)

echo.
echo ===================================
echo      Cleaning up build files
echo ===================================
echo.

rem Clean up temporary build files and folders
if exist "build" (
    echo Deleting build folder...
    rmdir /S /Q build
)

if exist "NetworkDriveManager.spec" (
    echo Deleting .spec file...
    del NetworkDriveManager.spec
)

echo.
echo ==============================================================
echo  Build successful!
echo  The executable is located in the 'dist' folder:
echo  dist\NetworkDriveManager.exe
echo ==============================================================
echo.
