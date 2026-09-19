# Setup Frame registry entries — Windows PowerShell native, tidak
# lewat .reg file (yang kadang bermasalah dengan escaping/encoding).

$ErrorActionPreference = "Stop"

$exe = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $exe) {
    $exe = (Get-Command python.exe).Source
    $exe = $exe -replace 'python\.exe$', 'pythonw.exe'
}

$icon = "D:\browser3\frame\data\ikon.ico"

if (-not (Test-Path $icon)) {
    Write-Host "[!] Icon not found: $icon" -ForegroundColor Red
    exit 1
}

Write-Host "[i] Python launcher: $exe"
Write-Host "[i] Icon: $icon"
Write-Host ""

# Bersihkan dulu
Remove-Item -Recurse -Force "HKCU:\Software\Frame" -ErrorAction Ignore
Remove-Item -Recurse -Force "HKCU:\Software\Classes\FrameHTTPS" -ErrorAction Ignore
Remove-Item -Recurse -Force "HKCU:\Software\Classes\FrameHTML" -ErrorAction Ignore
Remove-ItemProperty "HKCU:\Software\RegisteredApplications" -Name "Frame" -ErrorAction Ignore

# FrameHTML
New-Item -Path "HKCU:\Software\Classes\FrameHTML" -Force | Out-Null
Set-ItemProperty -Path "HKCU:\Software\Classes\FrameHTML" -Name "(Default)" -Value "Frame HTML Document"

New-Item -Path "HKCU:\Software\Classes\FrameHTML\DefaultIcon" -Force | Out-Null
Set-ItemProperty -Path "HKCU:\Software\Classes\FrameHTML\DefaultIcon" -Name "(Default)" -Value "`"$icon`",0"

New-Item -Path "HKCU:\Software\Classes\FrameHTML\shell\open\command" -Force | Out-Null
Set-ItemProperty -Path "HKCU:\Software\Classes\FrameHTML\shell\open\command" -Name "(Default)" -Value "`"$exe`" -m frame `"%1`""

# FrameHTTPS
New-Item -Path "HKCU:\Software\Classes\FrameHTTPS" -Force | Out-Null
Set-ItemProperty -Path "HKCU:\Software\Classes\FrameHTTPS" -Name "(Default)" -Value "Frame HTTPS Handler"

New-Item -Path "HKCU:\Software\Classes\FrameHTTPS\DefaultIcon" -Force | Out-Null
Set-ItemProperty -Path "HKCU:\Software\Classes\FrameHTTPS\DefaultIcon" -Name "(Default)" -Value "`"$icon`",0"

New-Item -Path "HKCU:\Software\Classes\FrameHTTPS\shell\open\command" -Force | Out-Null
Set-ItemProperty -Path "HKCU:\Software\Classes\FrameHTTPS\shell\open\command" -Name "(Default)" -Value "`"$exe`" -m frame `"%1`""

# RegisteredApplications
if (-not (Test-Path "HKCU:\Software\RegisteredApplications")) {
    New-Item -Path "HKCU:\Software\RegisteredApplications" -Force | Out-Null
}
Set-ItemProperty -Path "HKCU:\Software\RegisteredApplications" -Name "Frame" -Value "Software\Frame\Capabilities"

# Capabilities
New-Item -Path "HKCU:\Software\Frame\Capabilities" -Force | Out-Null
Set-ItemProperty -Path "HKCU:\Software\Frame\Capabilities" -Name "ApplicationName" -Value "Frame"
Set-ItemProperty -Path "HKCU:\Software\Frame\Capabilities" -Name "ApplicationDescription" -Value "Lightweight web browser built on PyQt6"
Set-ItemProperty -Path "HKCU:\Software\Frame\Capabilities" -Name "ApplicationIcon" -Value $icon

New-Item -Path "HKCU:\Software\Frame\Capabilities\URLAssociations" -Force | Out-Null
Set-ItemProperty -Path "HKCU:\Software\Frame\Capabilities\URLAssociations" -Name "http" -Value "FrameHTTPS"
Set-ItemProperty -Path "HKCU:\Software\Frame\Capabilities\URLAssociations" -Name "https" -Value "FrameHTTPS"

New-Item -Path "HKCU:\Software\Frame\Capabilities\FileAssociations" -Force | Out-Null
Set-ItemProperty -Path "HKCU:\Software\Frame\Capabilities\FileAssociations" -Name ".html" -Value "FrameHTML"
Set-ItemProperty -Path "HKCU:\Software\Frame\Capabilities\FileAssociations" -Name ".htm" -Value "FrameHTML"

# OpenWithProgids — supaya .html/.htm muncul di picker "Choose default
# by file type". Windows tidak auto-discover dari Capabilities untuk
# file type picker; harus eksplisit di sini.
foreach ($ext in @(".html", ".htm")) {
    $path = "HKCU:\Software\Classes\$ext\OpenWithProgids"
    New-Item -Path $path -Force | Out-Null
    New-ItemProperty -Path $path -Name "FrameHTML" -Value ([byte[]]@()) -PropertyType Binary -Force | Out-Null
}

# OpenWithProgids untuk protokol http/https — supaya Frame muncul
# di picker "How do you want to open this?" saat user klik link dari
# aplikasi yang tidak respect default handler.
foreach ($proto in @("http", "https")) {
    $path = "HKCU:\Software\Classes\$proto\OpenWithProgids"
    New-Item -Path $path -Force | Out-Null
    New-ItemProperty -Path $path -Name "FrameHTTPS" -Value ([byte[]]@()) -PropertyType Binary -Force | Out-Null
}

Write-Host "[OK] Registry entries written successfully." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Restart Explorer: Stop-Process -Name explorer -Force"
Write-Host "  2. Open Settings > Apps > Default apps"
Write-Host "  3. Search 'Frame' > Set default"