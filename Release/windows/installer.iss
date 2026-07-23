; Inno Setup script for Work Timer.
; Build with: build_installer.bat (requires Inno Setup: https://jrsoftware.org/isinfo.php)
; Prerequisite: run build_exe.bat first to produce dist\WorkTimer.exe

#define MyAppName "Work Timer"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "VladimirMenshikov"
#define MyAppExeName "WorkTimer.exe"

[Setup]
AppId={{7B2E7B7A-9C1E-4C3E-9C1E-B3B6F1B0WT01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\WorkTimer
DefaultGroupName=Work Timer
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=WorkTimerSetup-{#MyAppVersion}
SetupIconFile=assets\work-timer.ico
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "autostart"; Description: "Запускать Work Timer при входе в Windows"; GroupDescription: "Дополнительно:"
Name: "desktopicon"; Description: "Создать значок на рабочем столе"; GroupDescription: "Дополнительно:"

[Files]
Source: "dist\WorkTimer.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\.env.example"; DestDir: "{app}"; DestName: ".env.example"; Flags: ignoreversion

[Icons]
Name: "{group}\Work Timer"; Filename: "{app}\WorkTimer.exe"
Name: "{autodesktop}\Work Timer"; Filename: "{app}\WorkTimer.exe"; Tasks: desktopicon
Name: "{userstartup}\Work Timer"; Filename: "{app}\WorkTimer.exe"; Tasks: autostart

[Run]
Filename: "{app}\WorkTimer.exe"; Description: "Запустить Work Timer"; Flags: nowait postinstall skipifsilent

[Messages]
russian.BeveledLabel=Work Timer
