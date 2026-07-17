' Launches the PCocket relay hidden (no console window) at logon.
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\Users\BL9\Documents\pc-remote\relay"
sh.Run "node server.js", 0, False
