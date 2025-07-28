@echo off
echo Starting Langflow build and run process...

REM Check if .env file exists and set env file parameter
set "ENV_FILE_PARAM="
if exist "..\..\..env" (
    echo Found .env file, will pass to langflow run
    set "ENV_FILE_PARAM=--env-file "..\..\..env""
) else (
    echo .env file not found, langflow will use default configuration
)

echo.
echo Step 1: Installing frontend dependencies...
cd ..\..\src\frontend
if errorlevel 1 (
    echo Error: Could not navigate to src\frontend directory
    pause
    exit /b 1
)

echo Running npm install...
call npm install
if errorlevel 1 (
    echo Error: npm install failed
    pause
    exit /b 1
)

echo.
echo Step 2: Building frontend...
echo Running npm run build...
call npm run build
if errorlevel 1 (
    echo Error: npm run build failed
    pause
    exit /b 1
)

echo.
echo Step 3: Copying build files to backend...
cd ..\..

REM Check if build directory exists
if not exist "src\frontend\build" (
    if not exist "src\frontend\dist" (
        echo Error: Neither build nor dist directory found in src\frontend
        pause
        exit /b 1
    )
    set BUILD_DIR=src\frontend\dist
) else (
    set BUILD_DIR=src\frontend\build
)

echo Copying from %BUILD_DIR% to src\backend\base\langflow\frontend\
REM Create target directory if it doesn't exist
if not exist "src\backend\base\langflow\frontend" (
    mkdir "src\backend\base\langflow\frontend"
)

REM Remove existing files in target directory (FORCES CLEAN REPLACEMENT)
echo Removing existing files from target directory...
if exist "src\backend\base\langflow\frontend\*" (
    del /q /s "src\backend\base\langflow\frontend\*"
    for /d %%d in ("src\backend\base\langflow\frontend\*") do rmdir /s /q "%%d"
)

REM Copy all files from build directory
xcopy "%BUILD_DIR%\*" "src\backend\base\langflow\frontend\" /e /i /y
if errorlevel 1 (
    echo Error: Failed to copy build files
    pause
    exit /b 1
)

echo Build files copied successfully!

echo.
echo Step 4: Running Langflow...
echo.
echo Attention: Wait until uvicorn is running before opening the browser
echo.
if defined ENV_FILE_PARAM (
    uv run langflow run %ENV_FILE_PARAM%
) else (
    uv run langflow run
)
if errorlevel 1 (
    echo Error: Failed to run langflow
    pause
    exit /b 1
)

echo.
echo Langflow build and run process completed!
pause