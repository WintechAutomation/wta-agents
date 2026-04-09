# SSH Tunnel to LLM Server (autoreconnect)
# Local: localhost:5620 -> LLM:5620 (agent-channel)
# Reverse: LLM:5555 -> localhost:5555 (dashboard relay)
#
# Run: powershell -ExecutionPolicy Bypass -File ssh-tunnel-llm.ps1

$sshHost = "tiaworks@182.224.6.147"
$sshPort = 2222
$checkInterval = 30  # seconds between health checks
$logFile = "C:\MES\wta-agents\logs\ssh-tunnel-llm.log"

function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

Write-Log "SSH tunnel manager started"

while ($true) {
    # Check if tunnel is alive by testing local port
    $alive = $false
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("127.0.0.1", 5620)
        $tcp.Close()
        $alive = $true
    } catch {
        $alive = $false
    }

    if (-not $alive) {
        Write-Log "Tunnel down - (re)starting SSH tunnel"

        # Kill any existing ssh tunnel processes for this host
        Get-Process ssh -ErrorAction SilentlyContinue | Where-Object {
            $_.CommandLine -match "182.224.6.147" -and $_.CommandLine -match "5620"
        } | Stop-Process -Force -ErrorAction SilentlyContinue

        # Start new tunnel
        $sshArgs = @(
            "-p", $sshPort,
            "-o", "StrictHostKeyChecking=no",
            "-o", "ServerAliveInterval=30",
            "-o", "ServerAliveCountMax=3",
            "-o", "ExitOnForwardFailure=yes",
            "-N",
            "-L", "5620:localhost:5620",
            "-R", "5555:localhost:5555",
            $sshHost
        )

        Start-Process -FilePath "ssh" -ArgumentList $sshArgs -WindowStyle Hidden
        Write-Log "SSH tunnel started with -L 5620 -R 5555"
        Start-Sleep -Seconds 5
    }

    Start-Sleep -Seconds $checkInterval
}
