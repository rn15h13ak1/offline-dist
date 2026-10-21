@echo off
rem ===========================================================
rem  Update many tools at once. Put this file in the folder where
rem  the tools were cloned side by side, and double-click it:
rem
rem    C:\tools\update_all.bat
rem    C:\tools\docmold\         (git clone)
rem    C:\tools\path_lister\     (git clone)
rem
rem  Runs update.bat of each folder next to it that has .git,
rem  update.bat and undo_changes.bat. When some of them fail,
rem  lists them and asks Y. With Y, runs undo_changes.bat of each
rem  (it copies the changed files to backup\<date-time>\ in that
rem  folder first, then undoes them), and runs update.bat again.
rem
rem  With tool names as arguments, only those are updated:
rem    update_all.bat docmold path_lister
rem
rem  Messages here are ASCII on purpose: this file must stay
rem  readable in any console code page.
rem ===========================================================
setlocal

pushd "%~dp0" || (
    echo [ERROR] Cannot enter the folder of this script.
    pause
    exit /b 1
)

set RC=0
git --version >nul 2>&1 || (
    echo [ERROR] Git was not found. Install Git for Windows.
    set RC=1
    goto :done
)

set TOOLS=
set BAD=
if "%~1"=="" (
    for /d %%D in (*) do call :find "%%~nxD"
) else (
    for %%T in (%*) do call :named "%%~T"
)
if defined BAD (
    echo.
    echo [STOP] Nothing was changed.
    set RC=1
    goto :done
)
if not defined TOOLS (
    echo [STOP] No tool with update.bat is in this folder.
    echo        Put update_all.bat next to the folders of the tools.
    set RC=1
    goto :done
)

set DONE_OK=
set DONE_NG=
for %%T in (%TOOLS%) do call :update %%T

if not defined DONE_NG goto :summary
set "RETRY=%DONE_NG%"
echo.
echo ===========================================================
echo  Update failed:%RETRY%
echo ===========================================================
echo  When files of a tool were changed in its folder, update.bat
echo  stops. With Y, for each tool above, the changed files are
echo  copied to backup\^<date-time^>\ in its folder, undone, and
echo  update.bat is run again. Files that git does not track
echo  ^(settings, .venv\ ...^) are not touched.
echo.
set ANS=
set /p "ANS=Back up, undo and update again? [Y/N]: "
if /i not "%ANS%"=="Y" if /i not "%ANS%"=="YES" goto :summary

set DONE_NG=
set UNDO_NG=
for %%T in (%RETRY%) do call :undo %%T

:summary
echo.
echo ===========================================================
if defined DONE_OK echo [OK]   %DONE_OK%
if defined UNDO_NG echo [NG]   %UNDO_NG%  ^(could not undo^)
if defined DONE_NG echo [NG]   %DONE_NG%
echo ===========================================================
if defined DONE_NG set RC=1
if defined UNDO_NG set RC=1
goto :done

:done
popd
if not "%RC%"=="0" echo.& echo [exit code %RC%]
pause
exit /b %RC%

rem -----------------------------------------------------------
rem  :find "<folder>"  Take the folder when it is a cloned tool
rem -----------------------------------------------------------
:find
if not exist "%~1\.git" exit /b 0
if not exist "%~1\update.bat" exit /b 0
if not exist "%~1\undo_changes.bat" exit /b 0
rem Names are passed in a "for" list, so a space would split them.
set "N=%~1"
if not "%N: =%"=="%N%" (
    echo [SKIP] %~1  ^(a space in the folder name^)
    exit /b 0
)
set "TOOLS=%TOOLS% %~1"
exit /b 0

rem  :named "<tool>"  A tool given as an argument
:named
if not exist "%~1\update.bat" (
    echo [ERROR] %~1\update.bat is not in this folder.
    set BAD=1
    exit /b 0
)
call :find "%~1"
exit /b 0

rem -----------------------------------------------------------
rem  :update <tool>  Run update.bat of one tool
rem -----------------------------------------------------------
:update
echo.
echo ===========================================================
echo  %~1
echo ===========================================================
rem With an argument, update.bat does not pause.
call "%~dp0%~1\update.bat" unattended
if errorlevel 1 (
    set "DONE_NG=%DONE_NG% %~1"
) else (
    set "DONE_OK=%DONE_OK% %~1"
)
exit /b 0

rem -----------------------------------------------------------
rem  :undo <tool>  Back up and undo the changes, then update again
rem -----------------------------------------------------------
:undo
echo.
echo ===========================================================
echo  %~1  ^(undo_changes^)
echo ===========================================================
rem --yes: no question and no pause. It backs up before undoing.
call "%~dp0%~1\undo_changes.bat" --yes
if errorlevel 1 (
    set "UNDO_NG=%UNDO_NG% %~1"
    exit /b 0
)
call :update %1
exit /b 0
