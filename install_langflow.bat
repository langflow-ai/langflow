@echo off

:: Step 1: Install Python (if not installed)
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found, installing Python...
    curl -o python_installer.exe https://www.python.org/ftp/python/3.10.0/python-3.10.0-amd64.exe
    start /wait python_installer.exe /quiet InstallAllUsers=1 PrependPath=1
)

:: Step 2: Install pip (if not installed)
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Pip not found, installing pip...
    python -m ensurepip --upgrade
)

:: Step 3: Install/Upgrade Langflow
echo Installing or upgrading Langflow...
python -m pip install langflow -U

:: Step 4: Ask user to run Langflow
echo.
echo Shall I run Langflow? Press any key to continue or ESC to quit.
pause >nul

:: Check if ESC was pressed
if errorlevel 1 (
    echo Running Langflow...
    start python -m langflow run
) else (
    echo Exiting...
)

exit
