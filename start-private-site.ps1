$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendRoot = Join-Path $projectRoot "backend"
$frontendRoot = Join-Path $projectRoot "frontend"
$logRoot = Join-Path $projectRoot ".logs"
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$frontendEntry = Join-Path $frontendRoot ".output\server\index.mjs"
$urlFile = Join-Path $logRoot "private-site-url.txt"
$tunnelOut = Join-Path $logRoot "private-tunnel.stdout.log"
$tunnelErr = Join-Path $logRoot "private-tunnel.stderr.log"

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

function Test-HttpEndpoint([string]$Uri) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 5
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

function Wait-HttpEndpoint([string]$Uri, [int]$Seconds = 45) {
    for ($attempt = 0; $attempt -lt $Seconds; $attempt++) {
        if (Test-HttpEndpoint $Uri) { return }
        Start-Sleep -Seconds 1
    }
    throw "Service did not become ready: $Uri"
}

function Test-PublicTunnel([string]$Uri) {
    try {
        $hostname = ([uri]$Uri).Host
        $address = Resolve-DnsName $hostname -Type A -ErrorAction Stop |
            Where-Object IPAddress |
            Select-Object -First 1 -ExpandProperty IPAddress
        if (-not $address) { return $false }
        $status = & curl.exe --ssl-no-revoke -sS --max-time 15 -o NUL -w "%{http_code}" $Uri
        return [int]$status -ge 200 -and [int]$status -lt 500
    }
    catch {
        return $false
    }
}

if (-not (Test-HttpEndpoint "http://127.0.0.1:8000/api/health")) {
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        $pythonPath = (Get-Command python -ErrorAction Stop).Source
    }
    Start-Process -FilePath $pythonPath `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $backendRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logRoot "private-backend.stdout.log") `
        -RedirectStandardError (Join-Path $logRoot "private-backend.stderr.log") | Out-Null
    Wait-HttpEndpoint "http://127.0.0.1:8000/api/health"
}

if (-not (Test-HttpEndpoint "http://127.0.0.1:3000/login")) {
    if (-not (Test-Path -LiteralPath $frontendEntry)) {
        throw "Production frontend is missing. Run npm run build in frontend first."
    }
    $env:NITRO_HOST = "127.0.0.1"
    $env:NITRO_PORT = "3000"
    $env:NUXT_API_INTERNAL_BASE = "http://127.0.0.1:8000/api"
    Start-Process -FilePath (Get-Command node -ErrorAction Stop).Source `
        -ArgumentList @($frontendEntry) `
        -WorkingDirectory $frontendRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logRoot "private-frontend.stdout.log") `
        -RedirectStandardError (Join-Path $logRoot "private-frontend.stderr.log") | Out-Null
    Wait-HttpEndpoint "http://127.0.0.1:3000/login"
}

$existingUrl = if (Test-Path -LiteralPath $urlFile) { (Get-Content -LiteralPath $urlFile -Raw).Trim() } else { "" }
$existingTunnel = Get-CimInstance Win32_Process -Filter "Name = 'ssh.exe'" |
    Where-Object { $_.CommandLine -match 'localhost\.run' -and $_.CommandLine -match '80:127\.0\.0\.1:3000' } |
    Select-Object -First 1
if ($existingUrl -match '^https://[a-z0-9.-]+\.lhr\.life$' -and $existingTunnel -and (Test-PublicTunnel "$existingUrl/login")) {
    Write-Output $existingUrl
    exit 0
}

$sshPath = (Get-Command ssh -ErrorAction Stop).Source

$staleTunnels = Get-CimInstance Win32_Process -Filter "Name = 'ssh.exe'" |
    Where-Object { $_.CommandLine -match 'localhost\.run' -and $_.CommandLine -match '80:127\.0\.0\.1:3000' }
foreach ($tunnel in $staleTunnels) {
    Stop-Process -Id $tunnel.ProcessId -Force -ErrorAction SilentlyContinue
}

Remove-Item -LiteralPath $tunnelOut -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $tunnelErr -Force -ErrorAction SilentlyContinue
Start-Process -FilePath $sshPath `
    -ArgumentList @("-T", "-o", "StrictHostKeyChecking=accept-new", "-o", "ServerAliveInterval=30", "-o", "ExitOnForwardFailure=yes", "-R", "80:127.0.0.1:3000", "nokey@localhost.run") `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $tunnelOut `
    -RedirectStandardError $tunnelErr | Out-Null

$publicUrl = ""
for ($attempt = 0; $attempt -lt 45; $attempt++) {
    $logText = (Get-Content -LiteralPath $tunnelOut -Raw -ErrorAction SilentlyContinue) + "`n" +
        (Get-Content -LiteralPath $tunnelErr -Raw -ErrorAction SilentlyContinue)
    if ($logText -match 'https://[a-z0-9.-]+\.lhr\.life') {
        $publicUrl = $Matches[0]
        break
    }
    Start-Sleep -Seconds 1
}
if (-not $publicUrl) {
    throw "localhost.run did not return a tunnel URL. Check $tunnelOut and $tunnelErr"
}

Set-Content -LiteralPath $urlFile -Value $publicUrl -Encoding utf8
$remoteReady = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    if (Test-PublicTunnel "$publicUrl/login") {
        $remoteReady = $true
        break
    }
    Start-Sleep -Seconds 1
}
if (-not $remoteReady) {
    throw "Tunnel URL was created but failed the normal-DNS reachability check: $publicUrl"
}

$oldCloudflareTunnels = Get-CimInstance Win32_Process -Filter "Name = 'cloudflared.exe'" |
    Where-Object { $_.CommandLine -match 'tunnel' -and $_.CommandLine -match '127\.0\.0\.1:3000' }
foreach ($tunnel in $oldCloudflareTunnels) {
    Stop-Process -Id $tunnel.ProcessId -Force -ErrorAction SilentlyContinue
}
Write-Output $publicUrl
