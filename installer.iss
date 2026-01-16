#define AppName "MovilidadUCLM"
#define AppVer  "1.0"
#define AppExe  "MovilidadUCLM.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVer}
DefaultDirName={pf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=MovilidadUCLM_Installer
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
SetupIconFile=install_root\MovilidadUCLM.ico
UninstallDisplayIcon={app}\{#AppExe}
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "install_root\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "thirdparty\*;data_demo\*"
Source: "install_root\data_demo\*"; DestDir: "{localappdata}\MovilidadUCLM\data_demo"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "install_root\MovilidadUCLM.ico"; DestDir: "{app}"; Flags: ignoreversion

[Tasks]
Name: "desktopicon"; Description: "Crear icono en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\MovilidadUCLM.ico"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\MovilidadUCLM.ico"; Tasks: desktopicon

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\MovilidadUCLM"

[Dirs]
Name: "{localappdata}\MovilidadUCLM\logs"
Name: "{localappdata}\MovilidadUCLM\cache"
Name: "{localappdata}\MovilidadUCLM\config"
Name: "{localappdata}\MovilidadUCLM\data_demo"
Name: "{localappdata}\MovilidadUCLM\venv"

[Run]
Filename: "{cmd}"; \
  Parameters: "/C echo [SETUP_TRACE] Start >> ""{localappdata}\MovilidadUCLM\logs\setup_trace.log"""; \
  StatusMsg: "Inicializando..."; \
  Flags: waituntilterminated runhidden

Filename: "{cmd}"; \
  Parameters: "/C echo [SETUP_TRACE] Verificando Python 3.12 >> ""{localappdata}\MovilidadUCLM\logs\setup_trace.log"" && python --version >> ""{localappdata}\MovilidadUCLM\logs\setup_trace.log"" 2>&1"; \
  StatusMsg: "Verificando Python 3.12..."; \
  Flags: waituntilterminated runhidden; \
  Check: not (IsPython312Installed() or IsPython312OnPath())

Filename: "{cmd}"; \
  Parameters: "/C python -m venv ""{localappdata}\MovilidadUCLM\venv"" >> ""{localappdata}\MovilidadUCLM\logs\setup_trace.log"" 2>&1"; \
  StatusMsg: "Preparando entorno virtual..."; \
  Flags: waituntilterminated runhidden; \
  Check: not DirExists(ExpandConstant('{localappdata}\MovilidadUCLM\venv\Scripts'))

Filename: "{cmd}"; \
  Parameters: "/C if exist ""{localappdata}\MovilidadUCLM\venv\Scripts\python.exe"" (echo [SETUP_TRACE] venv ok >> ""{localappdata}\MovilidadUCLM\logs\setup_trace.log"") else (echo [SETUP_TRACE] ERROR: venv not found >> ""{localappdata}\MovilidadUCLM\logs\setup_trace.log"")"; \
  StatusMsg: "Verificando venv..."; \
  Flags: waituntilterminated runhidden

Filename: "{cmd}"; \
  Parameters: "/C (echo [pip_install.log] >> ""{localappdata}\MovilidadUCLM\logs\pip_install.log"" && ""{localappdata}\MovilidadUCLM\venv\Scripts\python.exe"" -m pip install --upgrade pip >> ""{localappdata}\MovilidadUCLM\logs\pip_install.log"" 2>&1 && ""{localappdata}\MovilidadUCLM\venv\Scripts\python.exe"" -m pip install --no-index --find-links ""{app}\wheelhouse"" -r ""{app}\requirements.lock.txt"" >> ""{localappdata}\MovilidadUCLM\logs\pip_install.log"" 2>&1)"; \
  StatusMsg: "Instalando dependencias (esto puede tardar varios minutos)..."; \
  Flags: waituntilterminated runhidden

Filename: "{cmd}"; \
  Parameters: "/C ""{localappdata}\MovilidadUCLM\venv\Scripts\python.exe"" -c ""import streamlit, flask; print('deps_ok')"" >> ""{localappdata}\MovilidadUCLM\logs\pip_install.log"" 2>&1"; \
  StatusMsg: "Validando dependencias..."; \
  Flags: waituntilterminated runhidden; \
  Check: DirExists(ExpandConstant('{localappdata}\MovilidadUCLM\venv\Scripts'))

Filename: "{cmd}"; \
  Parameters: "/C (echo [SETUP_TRACE] validate ok >> ""{localappdata}\MovilidadUCLM\logs\setup_trace.log"" && echo installed > ""{localappdata}\MovilidadUCLM\.installer_complete"")"; \
  StatusMsg: "Finalizando instalación..."; \
  Flags: waituntilterminated runhidden; \
  Check: DepsValidationOk()

Filename: "{app}\{#AppExe}"; \
  Description: "Abrir {#AppName}"; \
  Flags: nowait postinstall skipifsilent; \
  Check: DepsValidationOk()

[Code]
var
  DepsOk: Boolean;
  ValidationFailed: Boolean;
  PipErrorMsg: string;
  PipLogPath: string;
  SetupTracePath: string;

procedure TraceLog(const Msg: string);
begin
  if SetupTracePath = '' then
    SetupTracePath := ExpandConstant('{localappdata}\MovilidadUCLM\logs\setup_trace.log');
  ForceDirectories(ExtractFileDir(SetupTracePath));
  SaveStringToFile(SetupTracePath, GetDateTimeString('yyyy-mm-dd hh:nn:ss', '-', ':') + ' ' + Msg + #13#10, True);
end;

procedure PipLog(const Msg: string);
begin
  if PipLogPath = '' then
    PipLogPath := ExpandConstant('{localappdata}\MovilidadUCLM\logs\pip_install.log');
  ForceDirectories(ExtractFileDir(PipLogPath));
  SaveStringToFile(PipLogPath, GetDateTimeString('yyyy-mm-dd hh:nn:ss', '-', ':') + ' ' + Msg + #13#10, True);
end;

function GetPythonExePath(Value: string): string;
var
  InstallPath: string;
begin
  // Intentar encontrar Python en registry
  if RegQueryStringValue(HKLM, 'SOFTWARE\Python\PythonCore\3.12\InstallPath', '', InstallPath) or
     RegQueryStringValue(HKCU, 'SOFTWARE\Python\PythonCore\3.12\InstallPath', '', InstallPath) or
     RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Python\PythonCore\3.12\InstallPath', '', InstallPath) then
  begin
    Result := AddBackslash(InstallPath) + 'python.exe';
    TraceLog('Python en: ' + Result);
    Exit;
  end;
  // Si no está en registry, usar "python" del PATH
  Result := 'python.exe';
  TraceLog('Python: usando PATH (python.exe)');
end;

function IsPython312Installed(): Boolean;
var
  InstallPath: string;
begin
  Result :=
    RegQueryStringValue(HKLM, 'SOFTWARE\Python\PythonCore\3.12\InstallPath', '', InstallPath) or
    RegQueryStringValue(HKCU, 'SOFTWARE\Python\PythonCore\3.12\InstallPath', '', InstallPath) or
    RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Python\PythonCore\3.12\InstallPath', '', InstallPath);
end;

function IsPython312OnPath(): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec('cmd.exe', '/C python --version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

function DepsValidationOk(): Boolean;
var
  ResultCode: Integer;
  VenvPython: string;
begin
  VenvPython := ExpandConstant('{localappdata}\MovilidadUCLM\venv\Scripts\python.exe');
  
  TraceLog('Validating: ' + VenvPython);
  
  if not FileExists(VenvPython) then
  begin
    PipErrorMsg := 'venv\Scripts\python.exe no existe en: ' + VenvPython;
    TraceLog('ERROR: ' + PipErrorMsg);
    ValidationFailed := True;
    Result := False;
    Exit;
  end;

  Result := Exec(VenvPython, '-c "import streamlit, flask"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
  DepsOk := Result;
  
  if not Result then
  begin
    ValidationFailed := True;
    PipErrorMsg := 'Fallo al validar streamlit/flask (ResultCode=' + IntToStr(ResultCode) + '). Revisa los logs.';
    TraceLog('ERROR: validate failed - ResultCode=' + IntToStr(ResultCode));
  end
  else
  begin
    TraceLog('validate ok');
  end;
end;

function InitializeSetup(): Boolean;
var
  LogDir: string;
begin
  LogDir := ExpandConstant('{localappdata}\MovilidadUCLM\logs');
  ForceDirectories(LogDir);
  
  PipLogPath := LogDir + '\pip_install.log';
  SetupTracePath := LogDir + '\setup_trace.log';
  DepsOk := False;
  ValidationFailed := False;
  
  TraceLog('start');
  TraceLog('Windows: ' + GetWindowsVersionString());
  if Is64BitInstallMode() then
    TraceLog('Is64BitMode=True')
  else
    TraceLog('Is64BitMode=False');
  
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Msg: string;
  LastLogLine: string;
  LogContent: TArrayOfString;
begin
  if CurStep = ssPostInstall then
  begin
    if ValidationFailed or not DepsOk then
    begin
      Msg := 'No se pudieron instalar las dependencias necesarias (streamlit/flask).' + #13#10 + #13#10 +
             'Por favor, revisa los logs en:' + #13#10 +
             ExpandConstant('{localappdata}\MovilidadUCLM\logs\');
      if PipErrorMsg <> '' then
        Msg := Msg + #13#10 + #13#10 + 'Detalle: ' + PipErrorMsg;
      
      if FileExists(PipLogPath) and LoadStringsFromFile(PipLogPath, LogContent) then
      begin
        if Length(LogContent) > 0 then
          Msg := Msg + #13#10 + #13#10 + 'Última línea del log: ' + Trim(LogContent[High(LogContent)]);
      end;
      
      MsgBox(Msg, mbError, MB_OK);
      TraceLog('ERROR: installer incomplete - validation failed');
    end
    else
    begin
      TraceLog('complete ok');
    end;
  end;
end;
