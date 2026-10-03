@echo off
REM Activa los agentes autonomos de la E-Book Factory. Doble clic y sigue los pasos.
REM Paso 1: renovar el acceso de Claude para modo desatendido. Paso 2: comprobarlo. Paso 3: programar al jefe.
cd /d "%~dp0"
chcp 65001 >nul

echo.
echo ===== PASO 1/3: iniciar sesion en Claude =====
echo Se abrira el navegador. Pulsa "Autorizar" con tu cuenta (hiiinojosaa@gmail.com).
echo.
call claude auth login
if errorlevel 1 (
  echo.
  echo No se pudo iniciar sesion. Vuelve a ejecutar este archivo.
  pause
  exit /b 1
)

echo.
echo ===== PASO 2/3: comprobando que Claude funciona sin supervision =====
for /f "delims=" %%i in ('claude -p "Responde solo con la palabra PONG" 2^>^&1') do set RESP=%%i
echo Respuesta: %RESP%
echo %RESP% | findstr /i "PONG" >nul
if errorlevel 1 (
  echo.
  echo Claude sigue sin responder en modo desatendido. Copia el texto de arriba y mandaselo a Claude en el chat.
  pause
  exit /b 1
)

echo.
echo ===== PASO 3/3: programando al jefe cada 2 horas =====
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0SCRIPTS\schedule_autonomous_agents.ps1"
if errorlevel 1 (
  echo.
  echo Fallo al programar. Copia el error rojo de arriba y mandaselo a Claude en el chat.
  pause
  exit /b 1
)

echo.
echo Todo listo. Puedes cerrar esta ventana.
pause
