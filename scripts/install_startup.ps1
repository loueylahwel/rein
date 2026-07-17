$lnk = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\PCocket-Service.lnk"
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = "C:\Users\BL9\Documents\pc-remote\agent\dist\PCocket-Service.exe"
$s.WindowStyle = 7
$s.Save()
Write-Output "shortcut: $lnk"
