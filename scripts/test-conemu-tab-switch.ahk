#Requires AutoHotkey v2.0
#SingleInstance Force

; ConEmu 탭 전환 없이 특정 탭에 Enter 전송 테스트
; ConEmuC /GuiMacro:T<n> 로 탭 전환 없이 직접 키 전송

CONEMU_EXE := "C:\Program Files\ConEmu\ConEmuC.exe"
targetTab  := (A_Args.Length >= 1) ? Integer(A_Args[1]) : 2

MsgBox "탭 " targetTab " 에 화면 전환 없이 Enter 전송을 시도합니다.`n`n방법: ConEmuC /GuiMacro:T" targetTab " Keys(13)", "시작", 0x40

; ── 방법 A: Keys(13) — VK 13 = Enter ────────────────────────
try {
    RunWait '"' CONEMU_EXE '" /GuiMacro:T' targetTab ' Keys(13)',, "Hide"
}
Sleep 500
resultA := MsgBox("방법A: Keys(13) 실행 — 탭" targetTab "에 Enter가 입력됐나요?`n(해당 탭으로 직접 가서 확인)", "방법A 결과", 0x23)
if resultA = "Yes" {
    MsgBox "방법A 성공! (탭 전환 불필요, 직접 타겟 가능)", "완료", 0x40
    ExitApp
}

; ── 방법 B: Print(\n) ────────────────────────────────────────
try {
    RunWait '"' CONEMU_EXE '" /GuiMacro:T' targetTab ' Print("\n")',, "Hide"
}
Sleep 500
resultB := MsgBox("방법B: Print(`"\n`") 실행 — 탭" targetTab "에 Enter가 입력됐나요?", "방법B 결과", 0x23)
if resultB = "Yes" {
    MsgBox "방법B 성공!", "완료", 0x40
    ExitApp
}

; ── 방법 C: Tab(7,n) 으로 이동 후 WinActivate + Send Enter ──
MsgBox "방법C: Tab(7," targetTab ") 이동 후 WinActivate + Send Enter", "방법C 시도", 0x40
hwnd := WinExist("ahk_exe ConEmu64.exe")
hwndHex := Format("{:d}", hwnd)
try {
    RunWait '"' CONEMU_EXE '" /GuiMacro:' hwndHex ' Tab(7,' targetTab ')',, "Hide"
}
Sleep 800
WinActivate "ahk_id " hwnd
Sleep 300
Send "{Enter}"
Sleep 500
resultC := MsgBox("방법C 실행 — 탭" targetTab "으로 이동 + Enter 됐나요?", "방법C 결과", 0x23)
if resultC = "Yes" {
    MsgBox "방법C 성공!", "완료", 0x40
    ExitApp
}

MsgBox "모두 실패.", "결과", 0x10
ExitApp
