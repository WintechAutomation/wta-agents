#Requires AutoHotkey v2.0
#SingleInstance Force

; WTA Agent Plugin Auto-Approve
; ConEmu 4행×4열 split 각 분할 위치를 직접 클릭 -> 엔터 2회 전송
; 1회 순회, 16개 분할

CONEMU_TITLE := "WTA-Agents"

; 인수 파싱 (탭수 인수는 하위호환 유지, 실제로는 미사용)
initialWait := (A_Args.Length >= 2) ? Integer(A_Args[2]) : 8000

CLICK_WAIT   := 300   ; 클릭 후 안정화 대기 (ms)
ENTER_DELAY  := 150   ; 엔터 사이 대기 (ms)

HEADER_H     := 55    ; ConEmu 타이틀바 + 탭바 높이 (px, 근사값)
PANES        := 16    ; 분할 수 (4행 × 4열)

; 트레이 아이콘
try TraySetIcon "shell32.dll", 77

TrayTip "WTA Auto-Approve", "에이전트 로드 대기 중 (" (initialWait // 1000) "초)...", 3
Sleep initialWait

; ConEmu 창 확인
hwnd := WinExist("ahk_exe ConEmu64.exe")
if !hwnd
    hwnd := WinExist(CONEMU_TITLE)
if !hwnd {
    MsgBox "ConEmu 창을 찾을 수 없습니다 (제목: " CONEMU_TITLE ")", "WTA Auto-Approve", 0x10
    ExitApp
}

TrayTip "WTA Auto-Approve", "16개 분할 처리 시작", 2

; 창 위치/크기 계산
WinActivate "ahk_id " hwnd
WinWaitActive "ahk_id " hwnd, , 5
Sleep 300
WinGetPos &wx, &wy, &ww, &wh, "ahk_id " hwnd

contentTop := wy + HEADER_H
contentH   := wh - HEADER_H
paneW      := ww / 4
paneH      := contentH / 4

; 16개 분할 좌표 계산 (4행×4열, 행 우선 순서)
paneCoords := []
loop 4 {
    row := A_Index - 1
    loop 4 {
        col := A_Index - 1
        cx := Round(wx + col * paneW + paneW / 2)
        cy := Round(contentTop + row * paneH + paneH / 2)
        paneCoords.Push({x: cx, y: cy})
    }
}

loop PANES {
    paneIdx := A_Index
    coord   := paneCoords[paneIdx]

    ; 매 클릭 전 ConEmu 창 재활성화
    WinActivate "ahk_id " hwnd
    if !WinWaitActive("ahk_id " hwnd, , 3) {
        WinActivate "ahk_id " hwnd
        Sleep 300
    }

    ; 분할 클릭
    Click coord.x, coord.y
    Sleep CLICK_WAIT

    ; 엔터 2번
    Send "{Enter}"
    Sleep ENTER_DELAY
    Send "{Enter}"
    Sleep CLICK_WAIT
}

TrayTip "WTA Auto-Approve", "완료 - 16개 분할 처리됨. MAX reload-plugins 대기 중...", 3

; MAX가 마지막 pane (16번째) — 플러그인 로드 안정화 대기 후 /reload-plugins 전송
Sleep 30000

; MAX pane (마지막 = 16번째) 클릭
WinActivate "ahk_id " hwnd
WinWaitActive "ahk_id " hwnd, , 5
Sleep 300
maxCoord := paneCoords[PANES]
Click maxCoord.x, maxCoord.y
Sleep CLICK_WAIT

; /reload-plugins 입력 + 엔터
SendText "/reload-plugins"
Sleep 300
Send "{Enter}"

TrayTip "WTA Auto-Approve", "완료 - MAX /reload-plugins 전송됨", 3
Sleep 3000
ExitApp
