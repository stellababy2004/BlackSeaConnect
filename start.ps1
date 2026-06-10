Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

if (!(Test-Path ".\.venv\Scripts\python.exe")) {
    py -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

$env:FLASK_APP = "app.py"
.\.venv\Scripts\python.exe -m flask run --host 127.0.0.1 --port 5010
