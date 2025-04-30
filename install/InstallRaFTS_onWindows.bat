:: .batch script to install RaFTS in Windows environment
@echo off

:: title of command window
title RaFTS installation for Windows

:: Install UV package manager if not already installed
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo UV Package Manager not found. Installing UV Package Manager...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    
    :: Check if the installation succeeded
    if %errorlevel% neq 0 (
        echo Failed to install UV package manager. Exiting...
        pause
        exit /b 1
    )
) else (
    echo UV Package Manager is already installed.
)

:: open new terminal so uv available in environment
cmd /k
:: update UV package manager
echo Updating UV Package Manager...
uv self update

if %errorlevel% neq 0 (
    echo Failed to update UV package manager. Exiting...
    pause
    exit /b 1
)

:: Parse install_config.yml file
echo Reading installation configuration file: install_config.yml

powershell -Command ^
$Config = (Get-Content "install_config.yml" | ConvertFrom-Yaml); ^
$install_python = $Config.install_python; ^
$python_exe = $Config.python_exe; ^
$python_install_dir = $Config.python_install_dir ^

if (install_python -eq $true) { ^
    echo Installing Python version 3.12;
    if (-not $python_install_dir -match "" -or -not $python_install_dir -match "default") {
        uv python install 3.12 --install-dir $python_install_dir
    } else {
        uv python install 3.12
    }
    
    if ($LASTEXITCODE -ne 0) { ^
            echo Failed to install Python. Exiting...; ^
            exit /b 1; ^
        } else { ^
            echo Python installations complete. ^
    } 
} else {
    if (-not Test-Path -Path $python_exe) {
        echo Local python install specific by python_exe variable is not available. ^
        exit /b 1;
    }
    uv pip install --python $python_exe -r requirements.txt
}






