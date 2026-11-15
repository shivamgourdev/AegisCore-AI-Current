$ErrorActionPreference = "Stop"

$ProjectPath = "C:\Users\shiva\OneDrive\Desktop\AegisCore-AI"
Set-Location -LiteralPath $ProjectPath

$Python = Join-Path $ProjectPath ".venv\Scripts\python.exe"
$EvidencePath = Join-Path $ProjectPath "evidence\part-01-backend-foundation-verification.txt"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Virtual environment Python is missing."
}

function Write-Evidence {
    param([string]$Message)

    Write-Host $Message
    [System.IO.File]::AppendAllText(
        $EvidencePath,
        $Message + [Environment]::NewLine,
        $Utf8NoBom
    )
}

function Invoke-NativeCheck {
    param(
        [string]$Title,
        [string]$Executable,
        [string[]]$Arguments
    )

    Write-Evidence ""
    Write-Evidence "========== $Title =========="

    $Output = & $Executable @Arguments 2>&1
    $Code = $LASTEXITCODE

    foreach ($Line in $Output) {
        Write-Evidence ([string]$Line)
    }

    Write-Evidence "Exit code: $Code"

    if ($Code -ne 0) {
        throw "FAIL: $Title (exit code $Code)."
    }
}

try {
    $Header = @(
        "AEGISCORE AI - PART 1 VERIFICATION EVIDENCE"
        "Started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        "Project: $ProjectPath"
        ""
    ) -join [Environment]::NewLine

    [System.IO.File]::WriteAllText($EvidencePath, $Header, $Utf8NoBom)

    Invoke-NativeCheck `
        -Title "1. PYTHON VERSION" `
        -Executable $Python `
        -Arguments @("--version")

    Invoke-NativeCheck `
        -Title "2. DEPENDENCY CONSISTENCY" `
        -Executable $Python `
        -Arguments @("-m", "pip", "check")

    Invoke-NativeCheck `
        -Title "3. PYTHON SYNTAX" `
        -Executable $Python `
        -Arguments @("-m", "compileall", "-q", "backend\app\aegiscore", "backend\tests")

    Invoke-NativeCheck `
        -Title "4. AUTOMATED API TESTS" `
        -Executable $Python `
        -Arguments @("-m", "pytest", "-v")

    $ImportCode = "import sys; sys.path.insert(0, 'backend/app'); from aegiscore.main import app; print('Application:', app.title); print('Routes:', sorted([route.path for route in app.routes if hasattr(route, 'path')]))"

    Invoke-NativeCheck `
        -Title "5. APPLICATION IMPORT AND ROUTES" `
        -Executable $Python `
        -Arguments @("-c", $ImportCode)

    Write-Evidence ""
    Write-Evidence "========== 6. REQUIRED FILES =========="

    $RequiredFiles = @(
        "requirements.txt",
        "pyproject.toml",
        "backend\app\aegiscore\__init__.py",
        "backend\app\aegiscore\main.py",
        "backend\tests\test_health.py"
    )

    foreach ($RelativePath in $RequiredFiles) {
        $FullPath = Join-Path $ProjectPath $RelativePath

        if (-not (Test-Path -LiteralPath $FullPath -PathType Leaf)) {
            throw "Required file missing: $RelativePath"
        }

        Write-Evidence "[PASS] $RelativePath"
    }

    $Git = (Get-Command git -ErrorAction Stop).Source

    Invoke-NativeCheck `
        -Title "7. GIT STATUS" `
        -Executable $Git `
        -Arguments @("status", "--short")

    Write-Evidence ""
    Write-Evidence "FINAL RESULT: PASS"
    Write-Evidence "Completed: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
}
catch {
    Write-Evidence ""
    Write-Evidence "FINAL RESULT: FAIL"
    Write-Evidence $_.Exception.Message
    exit 1
}