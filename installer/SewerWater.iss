; Setup of the desktop app (user request 30-Oct-2026): everything it needs in one SewerWater_Setup.exe - the app
; packed by PyInstaller (dist\SewerWater: Python, its libraries, the pages, the data files), and Microsoft's WebView2
; bootstrapper run only where WebView2 is missing (it then installs it from the internet - user decision 30-Oct-2026).
; Installed for the user, no admin (%LOCALAPPDATA%\Programs\SewerWater), Start menu and Desktop shortcuts. The data
; is not here: the app asks for a master folder on its first run (app.py) and the uninstaller leaves it alone.
;     build_setup.bat  (PyInstaller, then ISCC installer\SewerWater.iss)  ->  dist\SewerWater_Setup.exe

#define AppName "Sewer & Water Network Design"
#define AppExe "SewerWater.exe"
#ifndef AppVersion
  ; build_setup.bat passes launcher\about.py APP_VERSION (/DAppVersion=...); this only when ISCC runs alone
  #define AppVersion "0.9.7"
#endif

[Setup]
AppId={{6F1A2C3E-9B47-4D21-A8E5-2F0C7D51B9A4}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Aurobindoji
AppPublisherURL=https://github.com/Aurobindoji/SewerWater
DefaultDirName={autopf}\SewerWater
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=SewerWater_Setup_{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\SewerWater\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "redist\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: NeedsWebView2

[InstallDelete]
; an older build's files (PyInstaller's _internal changes with every build)
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; Check: NeedsWebView2; \
  StatusMsg: "Installing Microsoft Edge WebView2 (internet needed) ..."; Flags: waituntilterminated
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
; the app's own update (menu App -> Check for updates, 10-Nov-2026) runs this setup silently: the app opens again
Filename: "{app}\{#AppExe}"; Flags: nowait postinstall runasoriginaluser; Check: WizardSilent

[Code]
const
  WV2 = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';   { the WebView2 runtime's id with Edge Update }

function HasWebView2(): Boolean;
var
  v: String;
begin
  Result := (RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\' + WV2, 'pv', v) and (v <> '') and (v <> '0.0.0.0'))
         or (RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WV2, 'pv', v) and (v <> '') and (v <> '0.0.0.0'))
         or (RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\' + WV2, 'pv', v) and (v <> '') and (v <> '0.0.0.0'));
end;

function NeedsWebView2(): Boolean;
begin
  Result := not HasWebView2();
end;
