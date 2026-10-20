# Interview Buddy — one-command launcher (Windows)
# Usage:  powershell -ExecutionPolicy Bypass -File run_interview_buddy.ps1
# PowerShell script to launch Interview Buddy
# It starts Ollama, the Python core (buddy‑core) and finally the Electron UI.
# The script keeps track of any core instance we start ourselves so we can clean it up on exit.
$root = Split-Path -Parent $MyInvocation.MyCommand.Path   # app/

$projectRoot = Split-Path -Parent $root                    # interview_buddy/

# Keep track of a core instance we start ourselves so we can clean it up on exit.
$coreProcess = $null
$startedCore = $false


Write-Host "== Interview Buddy ==" -ForegroundColor Cyan

# 1) Ollama running? (LLM + embeddings)
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama not found in PATH. Please ensure Ollama is installed and in your PATH." -ForegroundColor Red
    exit
}

# Check if ollama list succeeds; redirect errors properly in PowerShell
$ollamaRunning = $false
try {
    ollama list *>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $ollamaRunning = $true }
}
catch {}

if (-not $ollamaRunning) {
    Write-Host "Starting Ollama..." -ForegroundColor Yellow
    # Start Ollama in the background
    Start-Process ollama -ArgumentList "serve"
    
    Write-Host "Waiting for Ollama to initialize..." -ForegroundColor Yellow
    # Poll until Ollama is responsive or timeout after 15 seconds
    $timeout = 15
    $elapsed = 0
    while ($elapsed -lt $timeout) {
        try {
            ollama list *>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $ollamaRunning = $true
                break
            }
        }
        catch {}
        Start-Sleep -Seconds 2
        $elapsed += 2
    }
    
    if (-not $ollamaRunning) {
        Write-Host "Warning: Ollama took too long to start, continuing anyway..." -ForegroundColor Yellow
    }
}

# 2) buddy-core on :8790? (WASAPI loopback STT + RAG + answer engine)
$up =$false
try { Invoke-RestMethod http://127.0.0.1:8790/health -TimeoutSec 3 | Out-Null; $up =$true } catch {}
if (-not $up) {
    Write-Host "Starting buddy-core (first start loads STT model + embeds brain)..." -ForegroundColor Yellow
    # Run uvicorn as a package from the project root so relative imports work.
    # app/core/ has its own uv.lock, but the module path needs interview_buddy/ on sys.path.
    $uvicornArgs = @("run", "python", "-m", "uvicorn", "app.core.main:app", "--host", "127.0.0.1", "--port", "8790", "--log-level", "warning")
    $logOut = Join-Path $projectRoot 'core_output.log'
    $logErr = Join-Path $projectRoot 'core_error.log'
    
    # Fix: Pass an array to -ArgumentList so PowerShell handles quotes and spaces correctly
    $coreProcess = Start-Process -FilePath "cmd.exe" `
        -ArgumentList (@("/c", "uv") + $uvicornArgs) `
        -WorkingDirectory $projectRoot `
        -RedirectStandardOutput $logOut `
        -RedirectStandardError $logErr `
        -NoNewWindow `
        -PassThru
    $startedCore =$true

    # Poll until healthy (up to 60 s) so Electron's WebSocket start message isn't lost
    Write-Host "Waiting for buddy-core to become ready..." -ForegroundColor Yellow
    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline) {
        if ($coreProcess.HasExited) {
            Write-Host "buddy-core failed to start (process exited)." -ForegroundColor Red
            exit 1
        }
        Start-Sleep -Milliseconds 500
        try {
            $h = Invoke-RestMethod http://127.0.0.1:8790/health -TimeoutSec 2
            if ($h.stt -eq "ready") {
                Write-Host "buddy-core ready (stt=$($h.stt), chunks=$($h.brain_chunks))" -ForegroundColor Green
                break
            }
        }
        catch {}
    }
    
    if ($coreProcess.HasExited) {
        Write-Host "buddy-core failed to become ready within 60s." -ForegroundColor Red
        exit 1
    }
}
else {
    Write-Host "buddy-core already running on :8790" -ForegroundColor Green
}

# 3) Electron overlay app (dev mode)
Push-Location $root
try {
    # Run npm run dev in the current terminal.
    # This blocks the script until the app is closed, then cleanup runs.
    npm run dev
}
finally { Pop-Location }

# After electron exits, stop core if we started it
if ($startedCore) {
    Write-Host "Stopping buddy-core..."
    # Fix: Use taskkill /T /F to kill the entire process tree (uv + python workers)
    # This prevents leaving behind zombie processes holding port 8790.
    if ($coreProcess -and -not $coreProcess.HasExited) {
        taskkill /T /F /PID $coreProcess.Id 2>$null
    }
}