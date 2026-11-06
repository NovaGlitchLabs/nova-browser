; ============================================================
;  Nova Browser installer (Inno Setup, free: https://jrsoftware.org/isinfo.php)
;  1. Run build_app.bat first (makes dist\Nova Browser\).
;  2. Open this file in Inno Setup and press Build > Compile (Ctrl+F9).
;  3. Your installer appears in the "installer" folder: NovaBrowserSetup.exe
; ============================================================

[Setup]
AppId={{6E0A7C2B-4F1D-4B8E-9C3A-2D5F8B1E7A90}
AppName=Nova Browser
AppVersion=1.0
AppPublisher=Project Nova
DefaultDirName={localappdata}\Programs\Nova Browser
DefaultGroupName=Nova Browser
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=NovaBrowserSetup
SetupIconFile=nova.ico
UninstallDisplayIcon={app}\Nova Browser.exe
UninstallDisplayName=Nova Browser
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "startup"; Description: "Start Nova Browser when I sign in to Windows"; GroupDescription: "Extras:"; Flags: unchecked

[Files]
Source: "dist\Nova Browser\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Nova Browser"; Filename: "{app}\Nova Browser.exe"; AppUserModelID: "Nova.Browser"
Name: "{group}\Uninstall Nova Browser"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Nova Browser"; Filename: "{app}\Nova Browser.exe"; Tasks: desktopicon; AppUserModelID: "Nova.Browser"
Name: "{userstartup}\Nova Browser"; Filename: "{app}\Nova Browser.exe"; Tasks: startup

[Run]
Filename: "{app}\Nova Browser.exe"; Description: "Open Nova Browser now"; Flags: nowait postinstall skipifsilent

; Your bookmarks, history and settings live in %USERPROFILE%\.nova_browser and are kept if you uninstall.
