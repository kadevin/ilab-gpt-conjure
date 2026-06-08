param(
  [string]$Version = "",
  [string]$OutputDir = ".dist",
  [string]$PythonVersion = "3.11.9"
)

$ErrorActionPreference = "Stop"

$ProjectName = "ilab-gpt-conjure"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path

if ([System.IO.Path]::IsPathRooted($OutputDir)) {
  $BuildRoot = $OutputDir
} else {
  $BuildRoot = Join-Path $RepoRoot $OutputDir
}

if (-not $Version) {
  try {
    $Version = (git -C $RepoRoot describe --tags --always --dirty).Trim()
  } catch {
    $Version = Get-Date -Format "yyyyMMdd-HHmmss"
  }
}

$SafeVersion = ($Version -replace "[^A-Za-z0-9_.-]", "-").Trim("-")
if (-not $SafeVersion) {
  $SafeVersion = "dev"
}

$BundleName = "${ProjectName}_windows_portable_x64"
$BundleRoot = Join-Path $BuildRoot $BundleName
$AppDir = Join-Path $BundleRoot "app"
$PythonDir = Join-Path $BundleRoot "python"
$DataDir = Join-Path $BundleRoot "data"
$CacheDir = Join-Path $BuildRoot "_cache"
$ZipPath = Join-Path $BuildRoot "${BundleName}_${SafeVersion}.zip"
$HashPath = "${ZipPath}.sha256.txt"
$ManifestPath = Join-Path $BuildRoot "portable-build.json"

$PythonEmbedZip = "python-${PythonVersion}-embed-amd64.zip"
$PythonEmbedUrl = "https://www.python.org/ftp/python/${PythonVersion}/${PythonEmbedZip}"
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"

$AppItems = @(
  "codex_image",
  "assets",
  "requirements-webui.txt",
  "pyproject.toml",
  "README.md",
  "README.zh-CN.md",
  "LICENSE",
  "SECURITY.md",
  "CONTRIBUTING.md"
)

function Copy-AppItem {
  param(
    [string]$RelativePath
  )

  $Source = Join-Path $RepoRoot $RelativePath
  if (-not (Test-Path $Source)) {
    return
  }
  $Target = Join-Path $AppDir $RelativePath
  $TargetParent = Split-Path -Parent $Target
  New-Item -ItemType Directory -Force -Path $TargetParent | Out-Null
  Copy-Item -Path $Source -Destination $Target -Recurse -Force
}

function Remove-LocalArtifacts {
  param(
    [string]$Root
  )

  $Names = @("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".DS_Store")
  foreach ($Name in $Names) {
    Get-ChildItem -Path $Root -Recurse -Force -ErrorAction SilentlyContinue |
      Where-Object { $_.Name -eq $Name } |
      Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
  }
  Get-ChildItem -Path $Root -Recurse -Force -Include "*.pyc", "*.pyo" -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Force -Path $BuildRoot, $CacheDir | Out-Null
if (Test-Path $BundleRoot) {
  Remove-Item -Recurse -Force $BundleRoot
}
if (Test-Path $ZipPath) {
  Remove-Item -Force $ZipPath
}
if (Test-Path $HashPath) {
  Remove-Item -Force $HashPath
}

New-Item -ItemType Directory -Force -Path $AppDir, $PythonDir, $DataDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "logs") | Out-Null

foreach ($Item in $AppItems) {
  Copy-AppItem -RelativePath $Item
}

Copy-Item -Path (Join-Path $ScriptDir "portable_webui_app.py") -Destination (Join-Path $AppDir "portable_webui_app.py") -Force
Copy-Item -Path (Join-Path $ScriptDir "Start WebUI Portable.bat") -Destination (Join-Path $BundleRoot "Start WebUI Portable.bat") -Force
Copy-Item -Path (Join-Path $ScriptDir "README-portable.md") -Destination (Join-Path $BundleRoot "README-portable.md") -Force
Copy-Item -Path (Join-Path $ScriptDir "THIRD_PARTY_NOTICES.md") -Destination (Join-Path $BundleRoot "THIRD_PARTY_NOTICES.md") -Force
if (Test-Path (Join-Path $AppDir "LICENSE")) {
  Copy-Item -Path (Join-Path $AppDir "LICENSE") -Destination (Join-Path $BundleRoot "LICENSE") -Force
}
Remove-LocalArtifacts -Root $AppDir

$EmbedZipPath = Join-Path $CacheDir $PythonEmbedZip
if (-not (Test-Path $EmbedZipPath)) {
  Write-Host "Downloading $PythonEmbedUrl"
  Invoke-WebRequest -Uri $PythonEmbedUrl -OutFile $EmbedZipPath
}

Expand-Archive -Path $EmbedZipPath -DestinationPath $PythonDir -Force

$PythonPathFile = Get-ChildItem -Path $PythonDir -Filter "python*._pth" | Select-Object -First 1
if ($null -eq $PythonPathFile) {
  throw "Could not find python*._pth in embedded Python runtime."
}

$PathLines = Get-Content $PythonPathFile.FullName
$NextPathLines = New-Object System.Collections.Generic.List[string]
$HasAppPath = $false
$HasImportSite = $false
foreach ($Line in $PathLines) {
  if ($Line.Trim() -eq "..\app") {
    $HasAppPath = $true
  }
  if ($Line.Trim() -eq "import site" -or $Line.Trim() -eq "#import site") {
    if (-not $HasAppPath) {
      $NextPathLines.Add("..\app")
      $HasAppPath = $true
    }
    $NextPathLines.Add("import site")
    $HasImportSite = $true
    continue
  }
  $NextPathLines.Add($Line)
}
if (-not $HasAppPath) {
  $NextPathLines.Add("..\app")
}
if (-not $HasImportSite) {
  $NextPathLines.Add("import site")
}
Set-Content -Path $PythonPathFile.FullName -Value $NextPathLines -Encoding ASCII

$PythonExe = Join-Path $PythonDir "python.exe"
$GetPipPath = Join-Path $CacheDir "get-pip.py"
if (-not (Test-Path $GetPipPath)) {
  Write-Host "Downloading $GetPipUrl"
  Invoke-WebRequest -Uri $GetPipUrl -OutFile $GetPipPath
}

$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"
$env:PIP_NO_CACHE_DIR = "1"

& $PythonExe $GetPipPath --no-warn-script-location
& $PythonExe -m pip install --no-warn-script-location -r (Join-Path $AppDir "requirements-webui.txt")
$CertifiCaBundle = Join-Path $PythonDir "Lib\site-packages\certifi\cacert.pem"
if (-not (Test-Path $CertifiCaBundle)) {
  throw "certifi CA bundle was not installed at $CertifiCaBundle"
}
& $PythonExe -m pip freeze | Set-Content -Path (Join-Path $BundleRoot "python-requirements.lock.txt") -Encoding UTF8
& $PythonExe -c "import fastapi, uvicorn, multipart, httpx, PIL; import portable_webui_app; print('portable import ok')"

Compress-Archive -Path (Join-Path $BundleRoot "*") -DestinationPath $ZipPath -CompressionLevel Optimal
$Hash = Get-FileHash -Path $ZipPath -Algorithm SHA256
"$($Hash.Hash.ToLowerInvariant())  $(Split-Path -Leaf $ZipPath)" | Set-Content -Path $HashPath -Encoding ASCII

$Manifest = [ordered]@{
  project = $ProjectName
  version = $Version
  bundle = $BundleName
  zip = (Resolve-Path $ZipPath).Path
  sha256 = $Hash.Hash.ToLowerInvariant()
  python_version = $PythonVersion
}
$Manifest | ConvertTo-Json | Set-Content -Path $ManifestPath -Encoding UTF8

Write-Host "Built $ZipPath"
Write-Host "SHA256 $($Hash.Hash.ToLowerInvariant())"
