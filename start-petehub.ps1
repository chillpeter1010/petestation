$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendRoot = Join-Path $projectRoot 'backend'
$frontendRoot = Join-Path $projectRoot 'frontend'
$backendUrl = 'http://127.0.0.1:8000/api/health'
$frontendUrl = 'http://127.0.0.1:3000/'

function Test-PetehubEndpoint {
    param([Parameter(Mandatory)][string]$Url)

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 3
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 400
    }
    catch {
        return $false
    }
}

if (-not (Test-PetehubEndpoint -Url $backendUrl)) {
    $backendPython = Join-Path $backendRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $backendPython)) {
        throw "Backend Python not found: $backendPython"
    }

    Start-Process `
        -FilePath $backendPython `
        -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--reload') `
        -WorkingDirectory $backendRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $backendRoot 'uvicorn-start.stdout.log') `
        -RedirectStandardError (Join-Path $backendRoot 'uvicorn-start.stderr.log')
    Write-Host 'Starting backend on port 8000...'
}
else {
    Write-Host 'Backend is already healthy.'
}

if (-not (Test-PetehubEndpoint -Url $frontendUrl)) {
    $npmCommand = (Get-Command npm.cmd -ErrorAction Stop).Source
    Start-Process `
        -FilePath $npmCommand `
        -ArgumentList @('run', 'dev', '--', '--host', '127.0.0.1', '--port', '3000') `
        -WorkingDirectory $frontendRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $frontendRoot 'nuxt-dev.out.log') `
        -RedirectStandardError (Join-Path $frontendRoot 'nuxt-dev.err.log')
    Write-Host 'Starting frontend on port 3000...'
}
else {
    Write-Host 'Frontend is already healthy.'
}

$backendReady = $false
$frontendReady = $false
for ($attempt = 1; $attempt -le 40; $attempt++) {
    $backendReady = Test-PetehubEndpoint -Url $backendUrl
    $frontendReady = Test-PetehubEndpoint -Url $frontendUrl
    if ($backendReady -and $frontendReady) { break }
    Start-Sleep -Milliseconds 500
}

if (-not $backendReady) { throw 'Backend did not become healthy on port 8000.' }
if (-not $frontendReady) { throw 'Frontend did not become healthy on port 3000.' }

Write-Host 'Petehub is ready: http://127.0.0.1:3000/' -ForegroundColor Green
& (Join-Path $projectRoot 'open-homepage.cmd')
