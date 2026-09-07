Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

if (!(Test-Path ".\.venv\Scripts\python.exe")) {
    py -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

$env:ADMIN_USERNAME = $(if ([string]::IsNullOrWhiteSpace($env:ADMIN_USERNAME)) { "stella" } else { $env:ADMIN_USERNAME })
$env:ADMIN_PASSWORD = $(if ([string]::IsNullOrWhiteSpace($env:ADMIN_PASSWORD)) { "BSC_2026!VeryStrongPassword#Paris" } else { $env:ADMIN_PASSWORD })
$env:AI_SERVICE_REQUEST_TRIAGE_ENABLED = $(if ([string]::IsNullOrWhiteSpace($env:AI_SERVICE_REQUEST_TRIAGE_ENABLED)) { "1" } else { $env:AI_SERVICE_REQUEST_TRIAGE_ENABLED })
$env:OLLAMA_BASE_URL = $(if ([string]::IsNullOrWhiteSpace($env:OLLAMA_BASE_URL)) { "http://localhost:11434" } else { $env:OLLAMA_BASE_URL })
$env:OLLAMA_MODEL = $(if ([string]::IsNullOrWhiteSpace($env:OLLAMA_MODEL)) { "gemma3:4b" } else { $env:OLLAMA_MODEL })
$env:FLASK_APP = "app.py"
Write-Host "BlackSea Connect admin is ready at http://127.0.0.1:5010/admin"
Start-Process "http://127.0.0.1:5010/admin"
.\.venv\Scripts\python.exe -m flask run --host 127.0.0.1 --port 5010
