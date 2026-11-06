@echo off
rem Starts Nova Browser with no console window. Keep this file next to nova_browser.pyw.
cd /d "%~dp0"
start "" pythonw nova_browser.pyw
exit
