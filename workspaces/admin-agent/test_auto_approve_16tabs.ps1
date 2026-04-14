# WTA-Agents 자동 승인 시나리오 스크립트 (테스트용)
# 용도: 터미널 승인 대기 상태인 모든 에이전트 탭에 Enter 2번씩 전송
# 실행: powershell -File test_auto_approve_16tabs.ps1 -ConEmuPID <WTA-Agents ConEmu64 PID>

param([int]$ConEmuPID = 0)

$CONEMU_C = "C:\Program Files\ConEmu\ConEmu\ConEmuC64.exe"

# ConEmu PID 자동 감지 (미지정 시)
if ($ConEmuPID -eq 0) {
    $conemu_procs = Get-Process ConEmu64 -ErrorAction SilentlyContinue
    if ($conemu_procs.Count -eq 1) {
        $ConEmuPID = $conemu_procs[0].Id
    } else {
        Write-Output "ConEmu64 프로세스 여러 개 감지. -ConEmuPID 파라미터로 지정 필요:"
        $conemu_procs | ForEach-Object { Write-Output "  PID:$($_.Id)" }
        exit 1
    }
}

Write-Output "=== WTA-Agents 자동 승인 시작 ==="
Write-Output "대상 ConEmu64 PID: $ConEmuPID"

# 해당 ConEmu64의 자식 ConEmuC64 PID 목록 수집
$c64_list = Get-CimInstance Win32_Process | Where-Object {
    $_.ParentProcessId -eq $ConEmuPID -and $_.Name -eq 'ConEmuC64.exe'
} | Sort-Object ProcessId

Write-Output "에이전트 탭 수: $($c64_list.Count)"

if ($c64_list.Count -eq 0) {
    Write-Output "오류: 에이전트 탭을 찾을 수 없습니다."
    exit 1
}

# 방법1: 각 에이전트 PID로 직접 Enter 2번 전송 (탭 전환 없이도 동작)
$success = 0
$fail = 0

foreach ($c64 in $c64_list) {
    $agentPid = $c64.ProcessId

    # Enter 2번 전송
    $r1 = & $CONEMU_C -GuiMacro:$agentPid "Keys(Enter)"
    Start-Sleep -Milliseconds 300
    $r2 = & $CONEMU_C -GuiMacro:$agentPid "Keys(Enter)"

    if ($r1 -eq "OK" -and $r2 -eq "OK") {
        $success++
        Write-Output "  PID:$agentPid -> Enter x2 OK"
    } else {
        $fail++
        Write-Output "  PID:$agentPid -> FAIL (r1=$r1 r2=$r2)"
    }
    Start-Sleep -Milliseconds 200
}

Write-Output ""
Write-Output "=== 완료 ==="
Write-Output "성공: $success / 실패: $fail"
