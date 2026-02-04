#define AppName "MovilidadESII"
#define AppVer  "1.0"
#define AppExe  "MovilidadESII.exe"
#define PyInstallerExe "python-3.12.6-amd64.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher=TFG-MariaPicazoSanchez
DefaultDirName={localappdata}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=MovilidadESII_Installer
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
SetupLogging=yes
SetupIconFile=install_root\MovilidadESII.ico

[Dirs]
Name: "{app}\logs"
Name: "{app}\python"
Name: "{app}\venv"
Name: "{app}\data_demo"

[Files]
; Copia todo install_root EXCEPTO thirdparty y data_demo (que van aparte)
Source: "install_root\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "thirdparty\*;data_demo\*"

; Python installer solo al temp (y se borra al terminar)
Source: "install_root\thirdparty\{#PyInstallerExe}"; DestDir: "{tmp}"; Flags: deleteafterinstall

; Icono
Source: "install_root\MovilidadESII.ico"; DestDir: "{app}"; Flags: ignoreversion

; data_demo a AppData (4 excels)
Source: "install_root\data_demo\*.xlsx"; DestDir: "{app}\data_demo"; Flags: ignoreversion

; wheelhouse + requirements (offline pip)
Source: "install_root\wheelhouse\*"; DestDir: "{app}\wheelhouse"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "install_root\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userdesktop}\MovilidadESII"; \
  Filename: "{app}\MovilidadESII.exe"; \
  WorkingDir: "{app}"; \
  IconFilename: "{app}\MovilidadESII.ico"

Name: "{group}\MovilidadESII"; \
  Filename: "{app}\MovilidadESII.exe"; \
  WorkingDir: "{app}"; \
  IconFilename: "{app}\MovilidadESII.ico"


[Code]
var
  TracePath: string;
  PipLogPath: string;
  BasePythonExe: string;
  PySetupLogPath: string;

function AppDataBase(): string;
begin
  Result := ExpandConstant('{app}');
end;


function PyDir(): string;
begin
  Result := AppDataBase() + '\python';
end;

function PyExe(): string;
begin
  Result := PyDir() + '\python.exe';
end;

function VenvDir(): string;
begin
  Result := AppDataBase() + '\venv';
end;

function VenvPy(): string;
begin
  Result := VenvDir() + '\Scripts\python.exe';
end;

function Quote(const S: string): string;
begin
  Result := '"' + S + '"';
end;

procedure LogLine(const S: string);
begin
  SaveStringToFile(
    TracePath,
    GetDateTimeString('yyyy-mm-dd hh:nn:ss', '-', ':') + ' ' + S + #13#10,
    True
  );
end;

function ExecLogged(const Exe, Params, WorkDir: string; out RC: Integer): Boolean;
begin
  LogLine('Exec: ' + Exe + ' ' + Params);
  Result := Exec(Exe, Params, WorkDir, SW_HIDE, ewWaitUntilTerminated, RC);
  LogLine(' -> exit=' + IntToStr(RC));
end;

function RunCmdRedirect(const CmdLine, OutLog: string; out RC: Integer): Boolean;
var
  Params: string;
begin
  Params := '/C ' + Quote(CmdLine + ' > ' + Quote(OutLog) + ' 2>&1');
  LogLine('CMD: ' + Params);
  Result := Exec('cmd.exe', Params, '', SW_HIDE, ewWaitUntilTerminated, RC);
  LogLine(' -> exit=' + IntToStr(RC));
end;

procedure FailAndStop(const Msg: string);
begin
  LogLine('ERROR: ' + Msg);
  MsgBox(
    Msg + #13#10#13#10 +
    'Revisa logs en:' + #13#10 +
    AppDataBase() + '\logs',
    mbError, MB_OK
  );
end;

procedure EnsureLogs();
begin
  ForceDirectories(AppDataBase() + '\logs');
  TracePath := AppDataBase() + '\logs\setup_trace.log';
  PipLogPath := AppDataBase() + '\logs\pip_install.log';
  PySetupLogPath := AppDataBase() + '\logs\python_install.log';
  BasePythonExe := '';
end;

function FindPython312ByPaths(out PyPath: string): Boolean;
begin
  Result := False;
  PyPath := '';

  PyPath := PyExe();
  if FileExists(PyPath) then begin Result := True; exit; end;

  PyPath := ExpandConstant('{localappdata}\Programs\Python\Python312\python.exe');
  if FileExists(PyPath) then begin Result := True; exit; end;

  PyPath := ExpandConstant('{pf}\Python312\python.exe');
  if FileExists(PyPath) then begin Result := True; exit; end;

  PyPath := ExpandConstant('{pf32}\Python312\python.exe');
  if FileExists(PyPath) then begin Result := True; exit; end;

  PyPath := '';
end;

procedure InstallPythonIfMissing();
var
  RC: Integer;
  InstallerPath: string;
  Params: string;
  FoundPy: string;
begin
  if FileExists(PyExe()) then
  begin
    BasePythonExe := PyExe();
    LogLine('Python privado ya existe: ' + BasePythonExe);
    exit;
  end;

  InstallerPath := ExpandConstant('{tmp}\{#PyInstallerExe}');
  if not FileExists(InstallerPath) then
  begin
    FailAndStop('No encuentro el instalador de Python en: ' + InstallerPath);
    exit;
  end;

  ForceDirectories(PyDir());

  Params :=
    '/quiet InstallAllUsers=0 PrependPath=0 Include_pip=1 ' +
    'Include_launcher=0 Shortcuts=0 ' +
    'TargetDir=' + PyDir() + ' ' +
    'DefaultJustForMeTargetDir=' + PyDir() + ' ' +
    '/log ' + Quote(PySetupLogPath);

  LogLine('Instalando Python en: ' + PyDir());
  if (not ExecLogged(InstallerPath, Params, '', RC)) or (RC <> 0) then
  begin
    FailAndStop('Falló la instalación de Python (exit ' + IntToStr(RC) + ').');
    exit;
  end;

  if FileExists(PyExe()) then
  begin
    BasePythonExe := PyExe();
    LogLine('Python instalado en TargetDir: ' + BasePythonExe);
    exit;
  end;

  if FindPython312ByPaths(FoundPy) then
  begin
    BasePythonExe := FoundPy;
    LogLine('AVISO: Python no quedó en TargetDir. Usaré: ' + BasePythonExe);
    exit;
  end;

  FailAndStop(
    'Python se ejecutó (exit=0) pero no aparece ni en TargetDir ni en rutas típicas.' + #13#10 +
    'Revisa: ' + PySetupLogPath
  );
end;


procedure CreateVenvIfMissing();
var
  RC: Integer;
begin
  if FileExists(VenvPy()) then
  begin
    LogLine('Venv ya existe: ' + VenvPy());
    exit;
  end;

  if (BasePythonExe = '') or (not FileExists(BasePythonExe)) then
  begin
    FailAndStop('No existe Python base usable. Python localizado: ' + BasePythonExe);
    exit;
  end;

  ForceDirectories(VenvDir());

  if (not ExecLogged(BasePythonExe, '-m venv ' + Quote(VenvDir()), '', RC)) or (RC <> 0) then
  begin
    FailAndStop('Falló la creación del venv (exit ' + IntToStr(RC) + ').');
    exit;
  end;

  if not FileExists(VenvPy()) then
  begin
    FailAndStop('El venv quedó incompleto: falta ' + VenvPy());
    exit;
  end;
end;

procedure InstallDepsOffline();
var
  RC: Integer;
  Wheelhouse: string;
  Req: string;
  Cmd: string;
  FR: TFindRec;
begin
  Wheelhouse := ExpandConstant('{app}\wheelhouse');

  Req := ExpandConstant('{app}\requirements.txt');

  if not DirExists(Wheelhouse) then
  begin
    FailAndStop('No existe wheelhouse en: ' + Wheelhouse);
    exit;
  end;

  if not FileExists(Req) then
  begin
    FailAndStop('No existe requirements.runtime/lock/txt en: ' + Req);
    exit;
  end;

  if not FindFirst(Wheelhouse + '\setuptools-*.whl', FR) then
  begin
    FailAndStop('Falta setuptools-*.whl en wheelhouse. (offline pip no puede continuar)');
    exit;
  end else FindClose(FR);

  if not FindFirst(Wheelhouse + '\wheel-*.whl', FR) then
  begin
    FailAndStop('Falta wheel-*.whl en wheelhouse. (offline pip no puede continuar)');
    exit;
  end else FindClose(FR);

  ExecLogged(VenvPy(), '-m ensurepip --upgrade', '', RC);
  ExecLogged(VenvPy(), '-m pip install --upgrade pip', '', RC);

  Cmd := Quote(VenvPy()) + ' -m pip install --no-index --find-links ' + Quote(Wheelhouse) + ' pip setuptools wheel';
  RunCmdRedirect(Cmd, PipLogPath, RC);
  if RC <> 0 then
  begin
    FailAndStop('Falló la preinstalación de pip/setuptools/wheel. Mira pip_install.log.');
    exit;
  end;

  Cmd := Quote(VenvPy()) + ' -m pip install --no-index --find-links ' + Quote(Wheelhouse) + ' -r ' + Quote(Req);
  if (not RunCmdRedirect(Cmd, PipLogPath, RC)) or (RC <> 0) then
  begin
    FailAndStop('Falló la instalación de dependencias (pip). Mira pip_install.log.');
    exit;
  end;
end;

procedure ValidateCriticalImports();
var
  RC: Integer;
begin
  if (not ExecLogged(VenvPy(), '-c "import streamlit, flask, pandas"', '', RC)) or (RC <> 0) then
  begin
    FailAndStop('Fallo al validar imports (streamlit/flask/pandas). Revisa pip_install.log.');
    exit;
  end;
end;

procedure WriteMarkerOk();
var
  Marker: string;
begin
  Marker := AppDataBase() + '\.installer_complete';
  SaveStringToFile(Marker, 'ok', False);
  LogLine('Marker OK creado: ' + Marker);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    EnsureLogs();
    LogLine('POSTINSTALL start');

    InstallPythonIfMissing();
    LogLine('Python base seleccionado: ' + BasePythonExe);
    if (BasePythonExe = '') or (not FileExists(BasePythonExe)) then exit;

    CreateVenvIfMissing();
    if not FileExists(VenvPy()) then exit;

    InstallDepsOffline();
    ValidateCriticalImports();
    WriteMarkerOk();

    LogLine('POSTINSTALL end OK');
  end;
end;

[Run]
Filename: "{app}\venv\Scripts\pythonw.exe"; \
  Parameters: "-m streamlit run ""{app}\app.py"""; \
  Description: "Abrir {#AppName}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{localappdata}\MovilidadESII"
