# Locked-rebuild entry point. From repo root:
#   powershell -ExecutionPolicy Bypass -File .\scripts\rebuild.ps1
# New cut with Yahoo (VALID_AS_OF must already equal today):
#   powershell -ExecutionPolicy Bypass -File .\scripts\rebuild.ps1 -RefreshMarket
#
# Presentation (percent formats, Index fill, freeze, hidden sheets) is rewritten
# by the Python engine and gated by validate + adversarial_audit on every data row.
# Do not hand-edit the xlsx for leftover General / old-row green.
param(
    [switch]$RefreshMarket,
    [switch]$ForceRefresh
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Find-Python {
    $candidates = @(
        "D:\Users\zeyichen\AppData\Local\Programs\Python\Python314\python.exe",
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\python.exe")
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    foreach ($cmd in @("py", "python")) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($found) { return $found.Source }
    }
    throw "No Python 3.11+ found. Install 3.14 or add py launcher to PATH."
}

$py = Find-Python
Write-Host "python=$py"

& $py -m pip install -e . | Out-Host

$outName = & $py -c "from shareholder_list.build import output_filename; print(output_filename())"
if ($LASTEXITCODE -ne 0 -or -not $outName) { throw "could not get output filename" }
$outPath = Join-Path (Join-Path $Root "output") $outName.Trim()
New-Item -ItemType Directory -Force -Path (Join-Path $Root "output") | Out-Null

$cli = @("-m", "shareholder_list", "--audit", "--output", $outPath)
if ($RefreshMarket) { $cli += "--refresh-market" }
if ($ForceRefresh) { $cli += "--force-refresh" }

& $py @cli
exit $LASTEXITCODE
