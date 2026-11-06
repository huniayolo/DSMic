; DSMic telepítő (Inno Setup 6). Fordítás: ISCC.exe installer.iss
; A VB-CABLE-t nem csomagoljuk bele, telepítéskor a hivatalos oldalról töltődik le.

#define AppName "DSMic"
#define AppVersion "1.1"
#define CableUrl "https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack43.zip"

[Setup]
AppId={{6B1E5C0A-3D4F-4A57-9C21-D5A9E0F7B1C4}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=DSMic
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
OutputDir=.
OutputBaseFilename=DSMic_Setup
UninstallDisplayIcon={app}\DSMic.exe

[Languages]
Name: "hungarian"; MessagesFile: "compiler:Languages\Hungarian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[CustomMessages]
hungarian.TaskDesktop=Parancsikon az asztalra
hungarian.TaskGroupShortcuts=Parancsikonok:
hungarian.TaskCable=VB-CABLE virtuális hangkábel letöltése és telepítése (Discordhoz kell)
hungarian.TaskGroupDiscord=Discord támogatás:
hungarian.Uninstall=DSMic eltávolítása
hungarian.RunApp=DSMic indítása
hungarian.DownloadCaption=VB-CABLE letöltése a hivatalos vb-audio.com oldalról...
hungarian.DownloadFailed=A VB-CABLE letöltése nem sikerült:%n%1%n%nA DSMic telepítése folytatódik. A VB-CABLE-t később kézzel is telepítheted: https://vb-audio.com/Cable/
hungarian.UnzipFailed=A VB-CABLE csomag kicsomagolása nem sikerült.
hungarian.InstallingCable=VB-CABLE telepítése...
hungarian.CableNoStart=A VB-CABLE telepítője nem indult el.
english.TaskDesktop=Create a desktop shortcut
english.TaskGroupShortcuts=Shortcuts:
english.TaskCable=Download and install the VB-CABLE virtual audio cable (required for Discord)
english.TaskGroupDiscord=Discord support:
english.Uninstall=Uninstall DSMic
english.RunApp=Launch DSMic
english.DownloadCaption=Downloading VB-CABLE from the official vb-audio.com site...
english.DownloadFailed=Downloading VB-CABLE failed:%n%1%n%nDSMic setup will continue. You can install VB-CABLE manually later: https://vb-audio.com/Cable/
english.UnzipFailed=Could not extract the VB-CABLE package.
english.InstallingCable=Installing VB-CABLE...
english.CableNoStart=The VB-CABLE installer could not be started.
german.TaskDesktop=Desktop-Verknüpfung erstellen
german.TaskGroupShortcuts=Verknüpfungen:
german.TaskCable=VB-CABLE virtuelles Audiokabel herunterladen und installieren (für Discord erforderlich)
german.TaskGroupDiscord=Discord-Unterstützung:
german.Uninstall=DSMic deinstallieren
german.RunApp=DSMic starten
german.DownloadCaption=VB-CABLE wird von der offiziellen Seite vb-audio.com heruntergeladen...
german.DownloadFailed=Der Download von VB-CABLE ist fehlgeschlagen:%n%1%n%nDie Installation von DSMic wird fortgesetzt. Du kannst VB-CABLE später manuell installieren: https://vb-audio.com/Cable/
german.UnzipFailed=Das VB-CABLE-Paket konnte nicht entpackt werden.
german.InstallingCable=VB-CABLE wird installiert...
german.CableNoStart=Das VB-CABLE-Installationsprogramm konnte nicht gestartet werden.

[Tasks]
Name: "desktopicon"; Description: "{cm:TaskDesktop}"; GroupDescription: "{cm:TaskGroupShortcuts}"
Name: "installcable"; Description: "{cm:TaskCable}"; \
    GroupDescription: "{cm:TaskGroupDiscord}"; Check: not CableInstalled

[Files]
Source: "DSMic.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\DSMic"; Filename: "{app}\DSMic.exe"
Name: "{group}\{cm:Uninstall}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\DSMic"; Filename: "{app}\DSMic.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\DSMic.exe"; Description: "{cm:RunApp}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\reg.exe"; Parameters: "delete ""HKCU\Software\Microsoft\Windows\CurrentVersion\Run"" /v DSMic /f"; Flags: runhidden; RunOnceId: "DelAutostart"

[Code]
var
  DownloadPage: TDownloadWizardPage;
  CableDownloaded: Boolean;

function CableInstalled: Boolean;
var
  ResultCode: Integer;
begin
  { 0 = találat van a hangeszközök között }
  Result := Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoProfile -NonInteractive -Command "if (Get-CimInstance Win32_SoundDevice | Where-Object { $_.Name -like ''*VB-Audio Virtual Cable*'' }) { exit 0 } else { exit 1 }"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

function OnDownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  if Progress = ProgressMax then
    Log(Format('Downloaded: %s', [FileName]));
  Result := True;
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing),
    CustomMessage('DownloadCaption'), @OnDownloadProgress);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpReady) and WizardIsTaskSelected('installcable') then
  begin
    DownloadPage.Clear;
    DownloadPage.Add('{#CableUrl}', 'vbcable.zip', '');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
        CableDownloaded := True;
      except
        CableDownloaded := False;
        if DownloadPage.AbortedByUser then
          Log('Download aborted by user.')
        else
          SuppressibleMsgBox(FmtMessage(CustomMessage('DownloadFailed'), [GetExceptionMessage]),
            mbError, MB_OK, IDOK);
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;

procedure InstallCable;
var
  ResultCode: Integer;
  Dir, Setup: String;
begin
  Dir := ExpandConstant('{tmp}\vbcable');
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      '-NoProfile -NonInteractive -Command "Expand-Archive -LiteralPath ''' +
      ExpandConstant('{tmp}\vbcable.zip') + ''' -DestinationPath ''' + Dir + ''' -Force"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
  begin
    SuppressibleMsgBox(CustomMessage('UnzipFailed'), mbError, MB_OK, IDOK);
    Exit;
  end;

  if IsWin64 then
    Setup := Dir + '\VBCABLE_Setup_x64.exe'
  else
    Setup := Dir + '\VBCABLE_Setup.exe';

  WizardForm.StatusLabel.Caption := CustomMessage('InstallingCable');
  { -i = telepítés, -h = rejtett ablak. A Windows külön megerősítést kérhet az illesztőprogramhoz. }
  if not Exec(Setup, '-i -h', Dir, SW_SHOW, ewWaitUntilTerminated, ResultCode) then
    SuppressibleMsgBox(CustomMessage('CableNoStart'), mbError, MB_OK, IDOK);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and CableDownloaded then
    InstallCable;
end;
