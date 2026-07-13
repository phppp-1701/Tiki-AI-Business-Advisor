$ErrorActionPreference = 'Continue'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiDir   = Join-Path $repoRoot 'Tiki_Project\api'
$webDir   = Join-Path $repoRoot 'Tiki_Project\website'
$venvDir  = Join-Path $apiDir 'venv'

function Stop-PortProcesses {
    param([int[]]$Ports)
    foreach ($port in $Ports) {
        $portPattern = ":$port"
        try {
            $netstatLines = netstat -ano -p tcp 2>$null | Select-String -Pattern $portPattern | Select-String -Pattern "LISTENING"
        } catch { continue }
        $targets = @()
        foreach ($line in $netstatLines) {
            $parts = ($line.Line -split '\s+') | Where-Object { $_ -ne '' }
            if ($parts.Length -ge 5) { $targets += $parts[-1] }
        }
        $targets = $targets | Select-Object -Unique
        foreach ($target in $targets) {
            try {
                $proc = Get-Process -Id $target -ErrorAction Stop
                Stop-Process -Id $target -Force -ErrorAction Stop
                Write-Host "  Stopped PID $target ($($proc.ProcessName)) on port $port" -ForegroundColor Yellow
            } catch { }
        }
    }
}

function Write-Section { param([string]$Title)
    Write-Host ''
    Write-Host ('=' * 60) -ForegroundColor DarkCyan
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host ('=' * 60) -ForegroundColor DarkCyan
}
function Write-OK   { param([string]$Msg) Write-Host "  [OK]   $Msg" -ForegroundColor Green }
function Write-WARN { param([string]$Msg) Write-Host "  [WARN] $Msg" -ForegroundColor Yellow }
function Write-FAIL { param([string]$Msg) Write-Host "  [FAIL] $Msg" -ForegroundColor Red }
function Write-INFO { param([string]$Msg) Write-Host "  [INFO] $Msg" -ForegroundColor Gray }

Write-Section "TIKI BUSINESS ASSISTANT - Local Launcher"

if (-not (Test-Path $apiDir)) { Write-FAIL "API folder not found: $apiDir"; exit 1 }
if (-not (Test-Path $webDir)) { Write-FAIL "Website folder not found: $webDir"; exit 1 }

try {
    $pythonVersion = python --version 2>&1
    Write-OK "Python found: $pythonVersion"
} catch {
    Write-FAIL "Python is not installed or not in PATH"
    exit 1
}

Write-Section "Step 1/6: Cleaning old processes"
Stop-PortProcesses -Ports @(8000, 5501)
Write-OK "Ports 8000 and 5501 cleared"

Write-Section "Step 2/6: Virtual Environment"

$venvPython = Join-Path $venvDir 'Scripts\python.exe'
$venvPip    = Join-Path $venvDir 'Scripts\pip.exe'
$needsInstall = $false

if (-not (Test-Path $venvPython)) {
    Write-WARN "venv not found. Creating..."
    & python -m venv "$venvDir" 2>&1 | Out-Null
    if (-not (Test-Path $venvPython)) {
        Write-FAIL "Failed to create virtual environment"
        exit 1
    }
    $needsInstall = $true
    Write-OK "Virtual environment created"
} else {
    & $venvPython -c "import fastapi, pydantic, pandas, uvicorn" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-WARN "Some dependencies missing - will reinstall"
        $needsInstall = $true
    } else {
        Write-OK "Virtual environment OK (core packages present)"
    }
}

if ($needsInstall) {
    Write-INFO "Installing/updating dependencies..."
    & $venvPython -m pip install --upgrade pip --quiet 2>&1 | Out-Null
    $reqFile = Join-Path $apiDir 'requirements.txt'
    & $venvPip install -r $reqFile --quiet 2>&1 | Out-Null
    Write-OK "Dependencies installed"
}

Write-Section "Step 3/6: Checking .env Configuration"

$envFile = Join-Path $apiDir '.env'
if (-not (Test-Path $envFile)) {
    Write-FAIL ".env file not found at $envFile"
    exit 1
}

$envContent = Get-Content $envFile -Raw

if ($envContent -match 'GEMINI_API_KEY=(.+)') {
    $keyVal = $Matches[1].Trim()
    $preview = $keyVal.Substring(0, [Math]::Min(20, $keyVal.Length)) + "..."
    Write-OK "GEMINI_API_KEY configured: $preview"
} else {
    Write-FAIL "GEMINI_API_KEY not found in .env!"
    exit 1
}

if ($envContent -match 'GROQ_API_KEY=(.+)') {
    $groqCount = ($Matches[1].Trim() -split ',').Count
    Write-OK "GROQ_API_KEY: $groqCount key(s) configured"
} else {
    Write-WARN "GROQ_API_KEY not set (optional)"
}

foreach ($varName in @('DATA_PATH', 'MODELS_PATH', 'CHROMA_DB_PATH')) {
    if ($envContent -match "$varName=(.+)") {
        Write-OK "$varName = $($Matches[1].Trim())"
    } else {
        Write-WARN "$varName not set in .env"
    }
}

Write-Section "Step 4/6: Verifying Data and Models"

$env:PYTHONIOENCODING = 'utf-8'
$verifyScript = Join-Path $apiDir 'verify_setup.py'
if (Test-Path $verifyScript) {
    & $venvPython $verifyScript
    if ($LASTEXITCODE -ne 0) {
        Write-WARN "Some verification warnings (server will still start)"
    } else {
        Write-OK "All data and model checks passed"
    }
} else {
    Write-WARN "verify_setup.py not found - skipping"
}

Write-Section "Step 5/6: Starting Servers"

Write-INFO "Starting Backend API at http://localhost:8000 ..."
$venvPythonEsc = $venvPython -replace "'", "''"
$backendCmd = "& '$venvPythonEsc' main.py"
Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-Command', $backendCmd -WorkingDirectory $apiDir

Write-INFO "Waiting for backend to initialize..."
Start-Sleep -Seconds 4

Write-INFO "Starting Frontend at http://localhost:5501 ..."
$frontendCmd = "python -m http.server 5501"
Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-Command', $frontendCmd -WorkingDirectory $webDir

Write-Section "Step 6/6: Ready!"
Start-Sleep -Seconds 2
Start-Process 'http://localhost:5501'

Write-Host ''
Write-Host '  Architecture:' -ForegroundColor White
Write-Host '    Chat AI   : Gemini Flash (primary)' -ForegroundColor Green
Write-Host '    Backend   : http://localhost:8000' -ForegroundColor White
Write-Host '    Frontend  : http://localhost:5501' -ForegroundColor White
Write-Host '    API Docs  : http://localhost:8000/docs' -ForegroundColor White
Write-Host ''
Write-Host '  Troubleshooting:' -ForegroundColor Yellow
Write-Host '    1) Check Backend terminal for errors' -ForegroundColor Gray
Write-Host '    2) Verify GEMINI_API_KEY in Tiki_Project/api/.env' -ForegroundColor Gray
Write-Host ''
