$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    throw 'Create the virtual environment first using the README instructions.'
}
& '.\.venv\Scripts\python.exe' -m streamlit run app.py
