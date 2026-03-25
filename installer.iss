#define AppName "MovilidadESII"
#define AppVer  "1.0"
#define AppExe  "MovilidadESII.exe"
#define PyEmbedZip "python-3.12.6-embed-amd64.zip"

[Setup]
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher=María Picazo Sánchez
AppPublisherURL=https://github.com/MariaPicazoSanchez/TFG-MariaPicazoSanchez
AppCopyright=© 2026 María Picazo Sánchez — CC BY-NC 4.0
DefaultDirName={localappdata}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=MovilidadESII_Installer_ConData
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
SetupLogging=yes
SetupIconFile=install_root\MovilidadESII.ico
DisableDirPage=yes
CloseApplications=yes

[Dirs]
Name: "{app}\logs"
Name: "{app}\app"
Name: "{app}\runtime\python"
Name: "{app}\data"

[Files]
; Ejecutable compilado con PyInstaller (incluye todas sus dependencias)
Source: "dist\MovilidadESII\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "thirdparty\*;data_demo\*;wheelhouse\*"

; Copia todo install_root EXCEPTO thirdparty, data_demo, wheelhouse (que van a subcarpetas)
Source: "install_root\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "thirdparty\*;data_demo\*;wheelhouse\*;requirements.*.txt;__pycache__\*;_internal\*"

; Python embebido (zip) al temp
Source: "install_root\thirdparty\{#PyEmbedZip}"; DestDir: "{tmp}"; Flags: deleteafterinstall

; Icono
Source: "install_root\MovilidadESII.ico"; DestDir: "{app}"; Flags: ignoreversion

; data_demo a app/data/ (solo archivos, sin carpeta data_demo)
Source: "install_root\data_demo\*.xlsx"; DestDir: "{app}\data"; Flags: ignoreversion

; wheelhouse + requirements a app/runtime/
Source: "install_root\wheelhouse\*"; DestDir: "{app}\runtime\wheelhouse"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "install_root\requirements.txt";   DestDir: "{app}\runtime"; Flags: ignoreversion

[Icons]
Name: "{userdesktop}\MovilidadESII"; \
  Filename: "{app}\MovilidadESII.exe"; \
  Parameters: "--demo"; \
  WorkingDir: "{app}"; \
  IconFilename: "{app}\MovilidadESII.ico"

Name: "{group}\MovilidadESII"; \
  Filename: "{app}\MovilidadESII.exe"; \
  Parameters: "--demo"; \
  WorkingDir: "{app}"; \
  IconFilename: "{app}\MovilidadESII.ico"


[Code]
var
  TracePath: string;
  PipLogPath: string;
  BasePythonExe: string;

function AppDataBase(): string;
begin
  Result := ExpandConstant('{localappdata}\MovilidadESII');
end;

function PyDir(): string;
begin
  Result := AppDataBase() + '\runtime\python';
end;

function WheelhouseDir(): string;
begin
  Result := AppDataBase() + '\runtime\wheelhouse';
end;

function DataDir(): string;
begin
  Result := AppDataBase() + '\data';
end;

function BaseConfigPath(): string;
begin
  Result := AppDataBase() + '\config.json';
end;

function AppConfigPath(): string;
begin
  Result := AppDataBase() + '\app\config.json';
end;

function DemoConfigPath(): string;
begin
  Result := AppDataBase() + '\app\config.demo.json';
end;

function PyExe(): string;
begin
  Result := PyDir() + '\python.exe';
end;

function PipExe(): string;
begin
  Result := PyDir() + '\Scripts\pip.exe';
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
  BasePythonExe := '';
end;

procedure EnsureBaseConfig();
var
  ConfigContent: string;
  DataPath: string;
begin
  if FileExists(BaseConfigPath()) then
  begin
    LogLine('config.json ya existe en base');
    exit;
  end;

  DataPath := AppDataBase() + '\data';
  { Reemplazar \ por \\ para JSON válido }
  StringChangeEx(DataPath, '\', '\\', True);
  
  ConfigContent := '{' + #13#10 +
    '    "SICUE OUT": "' + DataPath + '\\SICUE OUT.xlsx",' + #13#10 +
    '    "Erasmus IN": "' + DataPath + '\\ERASMUS IN.xlsx",' + #13#10 +
    '    "Erasmus OUT": "' + DataPath + '\\ERASMUS OUT.xlsx",' + #13#10 +
    '}';

  if SaveStringToFile(BaseConfigPath(), ConfigContent, False) then
    LogLine('config.json creado con rutas absolutas')
  else
    LogLine('No se pudo crear config.json');
end;

procedure InstallPythonIfMissing();
var
  RC: Integer;
  ZipPath: string;
  PthFile: string;
begin
  if FileExists(PyExe()) then
  begin
    BasePythonExe := PyExe();
    LogLine('Python privado ya existe: ' + BasePythonExe);
    exit;
  end;

  ZipPath := ExpandConstant('{tmp}\{#PyEmbedZip}');
  if not FileExists(ZipPath) then
  begin
    FailAndStop('No encuentro el zip de Python en: ' + ZipPath);
    exit;
  end;

  ForceDirectories(PyDir());
  LogLine('Descomprimiendo Python embebido en: ' + PyDir());

  { Descomprimir usando PowerShell }
  if not ExecLogged(
    'powershell.exe',
    '-NoProfile -Command "Expand-Archive -Path ' + Quote(ZipPath) + ' -DestinationPath ' + Quote(PyDir()) + ' -Force"',
    '',
    RC
  ) or (RC <> 0) then
  begin
    FailAndStop('Falló la descompresión de Python (exit ' + IntToStr(RC) + ').');
    exit;
  end;

  if not FileExists(PyExe()) then
  begin
    FailAndStop('python.exe no encontrado después de descomprimir en: ' + PyExe());
    exit;
  end;

  { Habilitar pip en Python embebido: descomentar import site en python312._pth }
  PthFile := PyDir() + '\python312._pth';
  if FileExists(PthFile) then
  begin
    DeleteFile(PthFile);
    SaveStringToFile(PthFile, 'python312.zip' + #13#10 + '.' + #13#10 + 'import site' + #13#10, False);
    LogLine('Habilitado site-packages en python312._pth');
  end;

  BasePythonExe := PyExe();
  LogLine('Python embebido instalado: ' + BasePythonExe);
end;

procedure InstallGetPip();
var
  RC: Integer;
  GetPipUrl: string;
  GetPipPath: string;
begin
  if FileExists(PipExe()) then
  begin
    LogLine('pip ya está instalado');
    exit;
  end;

  LogLine('Instalando pip con get-pip.py...');
  GetPipPath := ExpandConstant('{tmp}\get-pip.py');
  GetPipUrl := 'https://bootstrap.pypa.io/get-pip.py';
  
  if not ExecLogged(
    'powershell.exe',
    '-NoProfile -Command "Invoke-WebRequest -Uri ' + GetPipUrl + ' -OutFile ' + Quote(GetPipPath) + '"',
    '',
    RC
  ) or (RC <> 0) then
  begin
    FailAndStop('Falló la descarga de get-pip.py (exit ' + IntToStr(RC) + ').');
    exit;
  end;

  if not ExecLogged(BasePythonExe, Quote(GetPipPath), '', RC) or (RC <> 0) then
  begin
    FailAndStop('Falló la instalación de pip (exit ' + IntToStr(RC) + ').');
    exit;
  end;

  LogLine('pip instalado correctamente');
end;

procedure InstallDepsOffline();
var
  RC: Integer;
  Wheelhouse: string;
  Req: string;
  Cmd: string;
  FR: TFindRec;
begin
  Wheelhouse := WheelhouseDir();

  Req := AppDataBase() + '\runtime\requirements.txt';

  if not DirExists(Wheelhouse) then
  begin
    FailAndStop('No existe wheelhouse en: ' + Wheelhouse);
    exit;
  end;

  if not FileExists(Req) then
  begin
    FailAndStop('No existe requirements.txt en: ' + Req);
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

  ExecLogged(BasePythonExe, '-m pip install --upgrade pip', '', RC);

  Cmd := Quote(BasePythonExe) + ' -m pip install --no-index --find-links ' + Quote(Wheelhouse) + ' pip setuptools wheel';
  RunCmdRedirect(Cmd, PipLogPath, RC);
  if RC <> 0 then
  begin
    FailAndStop('Falló la preinstalación de pip/setuptools/wheel. Mira pip_install.log.');
    exit;
  end;

  Cmd := Quote(BasePythonExe) + ' -m pip install --no-index --find-links ' + Quote(Wheelhouse) + ' -r ' + Quote(Req);
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
  if (not ExecLogged(BasePythonExe, '-c "import streamlit, flask, pandas"', '', RC)) or (RC <> 0) then
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

procedure CleanupInstallArtifacts();
var
  Wheelhouse: string;
  Req: string;
  AppDataDemo: string;
  AppThirdParty: string;
  AppWheelhouse: string;
begin
  Wheelhouse := WheelhouseDir();
  Req := AppDataBase() + '\runtime\requirements.txt';
  AppDataDemo := AppDataBase() + '\app\data_demo';
  AppThirdParty := AppDataBase() + '\app\thirdparty';
  AppWheelhouse := AppDataBase() + '\app\wheelhouse';

  if DirExists(Wheelhouse) then
  begin
    DelTree(Wheelhouse, True, True, True);
    LogLine('Limpieza: wheelhouse eliminado');
  end;

  if FileExists(Req) then
  begin
    DeleteFile(Req);
    LogLine('Limpieza: requirements.txt eliminado');
  end;

  if DirExists(AppDataDemo) then
  begin
    DelTree(AppDataDemo, True, True, True);
    LogLine('Limpieza: app\\data_demo eliminado');
  end;

  if DirExists(AppThirdParty) then
  begin
    DelTree(AppThirdParty, True, True, True);
    LogLine('Limpieza: app\\thirdparty eliminado');
  end;

  if DirExists(AppWheelhouse) then
  begin
    DelTree(AppWheelhouse, True, True, True);
    LogLine('Limpieza: app\\wheelhouse eliminado');
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    WizardForm.StatusLabel.Caption :=
      'Preparando el entorno de la aplicación... Esto puede tardar unos minutos.';
    WizardForm.StatusLabel.Update;
    EnsureLogs();
    LogLine('POSTINSTALL start');

    EnsureBaseConfig();

    InstallPythonIfMissing();
    LogLine('Python base seleccionado: ' + BasePythonExe);
    if (BasePythonExe = '') or (not FileExists(BasePythonExe)) then exit;

    InstallGetPip();

    InstallDepsOffline();
    ValidateCriticalImports();
    WriteMarkerOk();
    CleanupInstallArtifacts();

    LogLine('POSTINSTALL end OK');
  end;
end;



[Run]
Filename: "{app}\MovilidadESII.exe"; \
  Description: "Abrir {#AppName}"; \
  Parameters: "--demo"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{localappdata}\MovilidadESII"
