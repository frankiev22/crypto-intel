@echo off
REM ==========================================================================
REM  Hourly collector launcher for Windows Task Scheduler.
REM
REM  WHY THIS FILE EXISTS. The collector died 2026-09-15 05:07:59 UTC and every
REM  scheduled run after that fired, ran, and died on a Plan9 mount error. The
REM  CODE was never the problem - the launcher was. This path has no Claude
REM  sandbox in it at all, which is the entire fix.
REM
REM  CRYPTO_ORIGIN IS THE TRAP IN THIS JOB. Without it liveness.origin() returns
REM  "manual", and manual beats are SHOWN BUT NEVER COUNTED. The collector would
REM  look dead while running perfectly, and every paper close would misattribute.
REM  Verified 2026-09-18: unset -> "manual"; set -> "scheduled".
REM
REM  The stage list must stay equal to collect.staged_commands().
REM ==========================================================================

setlocal
set CRYPTO_ORIGIN=scheduled
set PY=C:\Python314\python.exe
set PROJ=C:\Users\Frankie\Desktop\Projects\crypto-intel
set LOGDIR=%PROJ%\data\_launcher
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set DSTAMP=%%c-%%a-%%b
set LOG=%LOGDIR%\collect.log

cd /d "%PROJ%" || exit /b 1

echo. >> "%LOG%"
echo ==== run started %DATE% %TIME% ==== >> "%LOG%"

for %%S in (scan sweep watchlist 1 6 24 168) do (
    echo --- stage %%S %TIME% >> "%LOG%"
    "%PY%" -X utf8 collect.py solana --stage %%S --max-seconds 110 >> "%LOG%" 2>&1
)

echo ==== run finished %DATE% %TIME% ==== >> "%LOG%"
endlocal
