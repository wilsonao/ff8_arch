@echo off
rem ============================================================
rem  FF8 Archipelago play session launcher (THE playthrough)
rem  Opens three windows: AP server, FF8 client, flight recorder.
rem  Safe to re-run each play session; server state persists in
rem  the .apsave next to the multidata. Close the windows (or
rem  Ctrl+C) to stop. Then launch FF8 via Junction VIII and play.
rem ============================================================
setlocal
set ROOT=%~dp0
set PY=%ROOT%.venv\Scripts\python.exe
set MULTI=
for %%f in ("%ROOT%output\playthrough\*.archipelago") do set MULTI=%%f
if "%MULTI%"=="" (
    echo No multidata found in output\playthrough - generate the seed first.
    pause
    exit /b 1
)
echo Multidata: %MULTI%
start "AP MultiServer" cmd /k ""%PY%" "%ROOT%Archipelago\MultiServer.py" "%MULTI%""
start "FF8 AP Client" cmd /k ""%PY%" "%ROOT%tools\run_client.py""
start "FF8 Flight Recorder" cmd /k ""%PY%" "%ROOT%tools\flight_recorder.py""
echo.
echo Server, client, and flight recorder started (three windows).
echo Now launch FF8 through Junction VIII and play. This window can be closed.
