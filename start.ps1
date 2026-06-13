Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

if (!(Test-Path ".\.venv\Scripts\python.exe")) {
    py -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

$env:ADMIN_USERNAME = $(if ([string]::IsNullOrWhiteSpace($env:ADMIN_USERNAME)) { "stella" } else { $env:ADMIN_USERNAME })
$env:ADMIN_PASSWORD = $(if ([string]::IsNullOrWhiteSpace($env:ADMIN_PASSWORD)) { "BSC_2026!VeryStrongPassword#Paris" } else { $env:ADMIN_PASSWORD })
$env:FLASK_APP = "app.py"
Write-Host "BlackSea Connect admin is ready at http://127.0.0.1:5010/admin"
Start-Process "http://127.0.0.1:5010/admin"
.\.venv\Scripts\python.exe -m flask run --host 127.0.0.1 --port 5010
