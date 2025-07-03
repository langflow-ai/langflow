#!/usr/bin/env pwsh

Write-Host "Starting Langflow build and run process..." -ForegroundColor Green

# Step 1: Build frontend
Write-Host "`nStep 1: Building frontend..." -ForegroundColor Yellow
try {
    Set-Location "..\..\src\frontend"
    Write-Host "Running npm run build..."
    npm run build
    if ($LASTEXITCODE -ne 0) {
        throw "npm run build failed"
    }
} catch {
    Write-Host "Error in frontend build: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Step 2: Copy build files
Write-Host "`nStep 2: Copying build files to backend..." -ForegroundColor Yellow
try {
    Set-Location "..\.."
    
    # Determine build directory
    $buildDir = if (Test-Path "src\frontend\build") {
        "src\frontend\build"
    } elseif (Test-Path "src\frontend\dist") {
        "src\frontend\dist"
    } else {
        throw "Neither build nor dist directory found in src\frontend"
    }
    
    $targetDir = "src\backend\base\langflow\frontend"
    Write-Host "Copying from $buildDir to $targetDir"
    
    # Create target directory if it doesn't exist
    if (-not (Test-Path $targetDir)) {
        New-Item -Path $targetDir -ItemType Directory -Force | Out-Null
    }
    
    # Remove existing files in target directory (FORCES CLEAN REPLACEMENT)
    Write-Host "Removing existing files from target directory..." -ForegroundColor Cyan
    if (Test-Path "$targetDir\*") {
        Remove-Item "$targetDir\*" -Recurse -Force
    }
    
    # Copy all files from build directory
    Copy-Item "$buildDir\*" -Destination $targetDir -Recurse -Force
    Write-Host "Build files copied successfully!" -ForegroundColor Green
    
} catch {
    Write-Host "Error copying files: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Step 3: Run Langflow
Write-Host "`nStep 3: Running Langflow..." -ForegroundColor Yellow
try {
    uv run langflow run
} catch {
    Write-Host "Error running langflow: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "`nLangflow build and run process completed!" -ForegroundColor Green
Read-Host "Press Enter to exit" 