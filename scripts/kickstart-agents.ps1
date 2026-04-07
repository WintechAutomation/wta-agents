# 각 에이전트 Claude Code 창에 초기 프롬프트 전송
$wshell = New-Object -ComObject wscript.shell
$agents = @(
    "nc-manager",
    "db-manager",
    "cs-agent",
    "sales-agent",
    "design-agent",
    "manufacturing-agent",
    "dev-agent",
    "admin-agent",
    "crafter",
    "issue-manager",
    "qa-agent"
)

foreach ($agent in $agents) {
    $windowTitle = "WTA-$agent"
    $activated = $wshell.AppActivate($windowTitle)
    if ($activated) {
        # 개발 채널 확인 프롬프트 자동 승인 (Enter)
        Start-Sleep -Milliseconds 500
        $wshell.SendKeys("{ENTER}")
        Write-Host "  [$agent] 개발 채널 승인 Enter 전송"
        Start-Sleep -Seconds 3

        # 한글 입력 문제를 피하기 위해 clipboard 사용
        $prompt = "시작. 너는 누구야? 이름과 역할을 MAX에게 send_message로 보고하고, wait_for_channel로 대기해."
        Set-Clipboard -Value $prompt
        $wshell.SendKeys("^v")
        Start-Sleep -Milliseconds 300
        $wshell.SendKeys("{ENTER}")
        Write-Host "[OK] $agent - 프롬프트 전송"
    } else {
        Write-Host "[FAIL] $agent - 창을 찾을 수 없음 ($windowTitle)"
    }
    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "완료. 각 에이전트 창에서 응답을 확인하세요."
