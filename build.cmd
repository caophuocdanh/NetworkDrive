rmdir /s /q dist
rmdir /s /q build
del /f *.spec

pyinstaller --onefile --windowed --icon=cloud.ico NetworkDrive.py