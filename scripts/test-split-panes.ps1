# ConEmu split pane test - 16 panes (4 rows x 4 cols)
$ConEmu = "C:\Program Files\ConEmu\ConEmu64.exe"

# Layout (4 rows x 4 cols):
# [ P1  | P2  | P3  | P4  ]
# [ P5  | P6  | P7  | P8  ]
# [ P9  | P10 | P11 | P12 ]
# [ P13 | P14 | P15 | P16 ]

$cmds = @(
    # ── Row 1 ──────────────────────────────────────────────
    "cmd /k echo PANE-01"
    "-new_console:s50V cmd /k echo PANE-02"
    "-new_console:s50V cmd /k echo PANE-03"
    "-new_console:s50V cmd /k echo PANE-04"

    # ── Row 2 ──────────────────────────────────────────────
    "-new_console:s50H cmd /k echo PANE-05"
    "-new_console:s50V cmd /k echo PANE-06"
    "-new_console:s50V cmd /k echo PANE-07"
    "-new_console:s50V cmd /k echo PANE-08"

    # ── Row 3 ──────────────────────────────────────────────
    "-new_console:s50H cmd /k echo PANE-09"
    "-new_console:s50V cmd /k echo PANE-10"
    "-new_console:s50V cmd /k echo PANE-11"
    "-new_console:s50V cmd /k echo PANE-12"

    # ── Row 4 ──────────────────────────────────────────────
    "-new_console:s50H cmd /k echo PANE-13"
    "-new_console:s50V cmd /k echo PANE-14"
    "-new_console:s50V cmd /k echo PANE-15"
    "-new_console:s50V cmd /k echo PANE-16"
)

$runlist = $cmds -join " ||| "
Write-Host "Launching 16-pane split test (4x4)..."
Start-Process -FilePath $ConEmu -ArgumentList "-Title", "SplitTest16", "-max", "-runlist", $runlist
Write-Host "Done."
