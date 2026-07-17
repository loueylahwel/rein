$lnk = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\PCocket-Relay.lnk"
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = "wscript.exe"
$s.Arguments = '"C:\Users\BL9\Documents\pc-remote\relay\start_relay.vbs"'
$s.WindowStyle = 7
$s.Save()
Write-Output "shortcut: $lnk"
