$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!(Test-Path .venv/Scripts/python.exe)) {
    python -m venv .venv
    if ($LASTEXITCODE) { throw 'Environment creation failed' }
}
& .venv/Scripts/python.exe -m ensurepip --upgrade
if ($LASTEXITCODE) { throw 'pip setup failed' }
& .venv/Scripts/python.exe -m pip install -r requirements-build.txt
if ($LASTEXITCODE) { throw 'Dependency installation failed' }
& .venv/Scripts/python.exe -m playwright install chromium
if ($LASTEXITCODE) { throw 'Browser installation failed' }
& .venv/Scripts/python.exe -m unittest -v test_app test_scanner
if ($LASTEXITCODE) { throw 'Tests failed' }
& .venv/Scripts/python.exe -m PyInstaller --noconfirm --onefile --windowed --name AutoMoochReddit --icon "$PSScriptRoot/assets/AutoMooch.ico" --add-data "$PSScriptRoot/assets;assets" --distpath releases --workpath build/pyinstaller --specpath build --collect-all playwright app.py
if ($LASTEXITCODE) { throw 'Executable build failed' }
& .venv/Scripts/python.exe -m PyInstaller --noconfirm --onefile --windowed --name SubredditScanner --icon "$PSScriptRoot/assets/AutoMooch.ico" --add-data "$PSScriptRoot/assets;assets" --distpath releases --workpath build/scanner --specpath build --collect-all playwright subreddit_scanner.py
if ($LASTEXITCODE) { throw 'Scanner executable build failed' }
$checksums = foreach ($name in @('AutoMoochReddit.exe', 'SubredditScanner.exe')) {
    $digest = (Get-FileHash "releases/$name" -Algorithm SHA256).Hash.ToLowerInvariant()
    "$digest  $name"
}
$checksums | Set-Content -Encoding ascii releases/SHA256SUMS.txt
