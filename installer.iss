#define AppName "MovilidadUCLM"
#define AppVer  "1.0"
#define AppExe  "MovilidadUCLM.exe"
#define PyExe   "python-3.12.6-arm64.exe"

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

[Files]
; Copia toda la app a Program Files, excepto thirdparty
Source: "install_root\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "thirdparty\*"

; Copia el instalador de Python al TEMP para ejecutarlo durante la instalación
Source: "install_root\thirdparty\{#PyExe}"; DestDir: "{tmp}"; Flags: deleteafterinstall

; Asegurarse de que el icono se copie correctamente
Source: "install_root\MovilidadUCLM.ico"; DestDir: "{app}"; Flags: ignoreversion

; Incluir el archivo config.toml en la instalación
Source: "install_root\.streamlit\config.toml"; DestDir: "{app}\.streamlit"; Flags: ignoreversion

[Tasks]
Name: "desktopicon"; Description: "Crear icono en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\MovilidadUCLM.ico"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\MovilidadUCLM.ico"; Tasks: desktopicon

[Run]
; Instala Python 3.12 SOLO si no se detecta en el sistema
Filename: "{tmp}\{#PyExe}"; \
  Parameters: "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0"; \
  StatusMsg: "Instalando Python 3.12..."; \
  Flags: waituntilterminated; \
  Check: not (IsPython312Installed() or IsPython312OnPath())

; Lanza tu app al final
Filename: "{app}\{#AppExe}"; Description: "Abrir {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
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
  // Comprueba que "python" existe y que es 3.12
  Result :=
    Exec(
      'cmd.exe',
      '/C python -c "import sys; raise SystemExit(0 if sys.version_info[:2]==(3,12) else 1)"',
      '',
      SW_HIDE,
      ewWaitUntilTerminated,
      ResultCode
    ) and (ResultCode = 0);
end;
