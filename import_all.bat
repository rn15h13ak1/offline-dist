@echo off
rem ===========================================================
rem  Import many tools at once. Double-click it.
rem
rem  For each tool listed in import_all.txt, finds its zip
rem  (<tool>-offline.zip or <tool>\<tool>-offline.zip), extracts
rem  it to a temporary folder, and runs its import.bat with the
rem  folder of the Git repositories given in import_all.txt.
rem  A tool whose zip is not here is skipped.
rem
rem  import_all.txt is the definition to edit here. When it is
rem  missing, it is made from import_all.example.txt.
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
set WORK=
set "DEF=%~dp0import_all.txt"
set "EXAMPLE=%~dp0import_all.example.txt"

if exist "%DEF%" goto :havedef
if not exist "%EXAMPLE%" (
    echo [ERROR] Neither import_all.txt nor import_all.example.txt is here.
    set RC=1
    goto :done
)
copy /y "%EXAMPLE%" "%DEF%" >nul || ( set RC=1& goto :done )
echo Made import_all.txt from import_all.example.txt.
echo Edit it ^(the folder of the Git repositories, and the tools^),
echo save it, and run import_all.bat again.
start "" notepad "%DEF%"
goto :done
:havedef

rem Read the definition as UTF-8, so a folder name in Japanese is
rem read right. The code page is set back right after.
set CP=
for /f "tokens=2 delims=:" %%C in ('chcp') do set "CP=%%C"
chcp 65001 >nul 2>&1
set ROOT=
set "ZIPDIR=%~dp0"
set TOOLS=
set BAD=
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%DEF%") do call :defline "%%A" "%%B"
if defined CP chcp %CP% >nul 2>&1
if defined BAD (
    echo.
    echo [STOP] Fix the lines above in import_all.txt. Nothing was changed.
    set RC=1
    goto :done
)
if not defined TOOLS (
    echo [STOP] No tool is listed in import_all.txt. Nothing was changed.
    set RC=1
    goto :done
)
if "%ZIPDIR:~-1%"=="\" set "ZIPDIR=%ZIPDIR:~0,-1%"
if not exist "%ZIPDIR%\" (
    echo [ERROR] ZIPDIR not found: %ZIPDIR%
    set RC=1
    goto :done
)

set "WORK=%TEMP%\offline-import-all-%RANDOM%%RANDOM%"
mkdir "%WORK%" || ( set RC=1& goto :done )

set DONE_OK=
set DONE_NG=
set DONE_SKIP=
for %%T in (%TOOLS%) do call :one %%T

echo.
echo ===========================================================
if defined DONE_OK   echo [OK]   %DONE_OK%
if defined DONE_NG   echo [NG]   %DONE_NG%
if defined DONE_SKIP echo [SKIP] %DONE_SKIP%  ^(no zip^)
echo ===========================================================
if defined DONE_NG set RC=1
goto :done

:done
if defined WORK if exist "%WORK%" rmdir /s /q "%WORK%"
popd
if not "%RC%"=="0" echo.& echo [exit code %RC%]
pause
exit /b %RC%

rem -----------------------------------------------------------
rem  :defline "<before =>" "<after =>"  One line of import_all.txt
rem -----------------------------------------------------------
:defline
set "K=%~1"
set "V=%~2"
call :trim K
call :trim V
if not defined K exit /b 0
rem A comment after a byte order mark at the top of the file.
if not "%K:#=%"=="%K%" exit /b 0
if /i "%K%"=="ROOT" (
    set "ROOT=%V%"
    exit /b 0
)
if /i "%K%"=="ZIPDIR" (
    if defined V set "ZIPDIR=%V%"
    exit /b 0
)
if not "%K: =%"=="%K%" (
    echo [ERROR] Not understood: %K%
    echo         Write ^<tool^> or ^<tool^>=^<folder^>, one per line.
    set BAD=1
    exit /b 0
)
set "TOOLS=%TOOLS% %K%"
set "ROOT_%K%=%V%"
exit /b 0

rem  :trim <name>  Drop spaces and tabs at both ends of a variable
:trim
setlocal EnableDelayedExpansion
set "T=!%1!"
:trimhead
if not defined T goto :trimend
if "!T:~0,1!"==" " ( set "T=!T:~1!" & goto :trimhead )
if "!T:~0,1!"=="	" ( set "T=!T:~1!" & goto :trimhead )
:trimtail
if not defined T goto :trimend
if "!T:~-1!"==" " ( set "T=!T:~0,-1!" & goto :trimtail )
if "!T:~-1!"=="	" ( set "T=!T:~0,-1!" & goto :trimtail )
:trimend
endlocal & set "%1=%T%"
exit /b 0

rem -----------------------------------------------------------
rem  :one <tool>  Extract the zip of one tool and run its import.bat
rem -----------------------------------------------------------
:one
set "TOOL=%~1"
echo.
echo ===========================================================
echo  %TOOL%
echo ===========================================================
set ZIP=
if exist "%ZIPDIR%\%TOOL%-offline.zip" set "ZIP=%ZIPDIR%\%TOOL%-offline.zip"
if not defined ZIP if exist "%ZIPDIR%\%TOOL%\%TOOL%-offline.zip" set "ZIP=%ZIPDIR%\%TOOL%\%TOOL%-offline.zip"
if not defined ZIP (
    echo [SKIP] %TOOL%-offline.zip is not in %ZIPDIR%
    set "DONE_SKIP=%DONE_SKIP% %TOOL%"
    exit /b 0
)

call set "R=%%ROOT_%TOOL%%%"
if not defined R set "R=%ROOT%"
if not defined R (
    echo [ERROR] No folder of the Git repositories for %TOOL%.
    echo         Write ROOT=^<folder^> or %TOOL%=^<folder^> in import_all.txt.
    set "DONE_NG=%DONE_NG% %TOOL%"
    exit /b 0
)
set R=%R:"=%
if "%R:~-1%"=="\" set "R=%R:~0,-1%"
if not exist "%R%\" (
    echo [ERROR] Folder not found: %R%
    set "DONE_NG=%DONE_NG% %TOOL%"
    exit /b 0
)

set "DEST=%WORK%\%TOOL%"
echo Extracting %ZIP%
call :extract
if not exist "%DEST%\import.bat" (
    echo [ERROR] Cannot extract %ZIP%
    set "DONE_NG=%DONE_NG% %TOOL%"
    exit /b 0
)

rem With the folder given, import.bat neither asks for it nor pauses.
rem It still asks Y (to create the repository) or KEEP (on a conflict).
call "%DEST%\import.bat" "%R%"
if errorlevel 1 (
    set "DONE_NG=%DONE_NG% %TOOL%"
) else (
    set "DONE_OK=%DONE_OK% %TOOL%"
)
rmdir /s /q "%DEST%" 2>nul
exit /b 0

rem  :extract  ZIP into DEST. PowerShell first, then tar (Windows 10+).
:extract
powershell -NoProfile -NonInteractive -Command "$ErrorActionPreference='Stop'; Expand-Archive -LiteralPath $env:ZIP -DestinationPath $env:DEST -Force" >nul 2>&1
if exist "%DEST%\import.bat" exit /b 0
if exist "%DEST%" rmdir /s /q "%DEST%"
mkdir "%DEST%" 2>nul
tar -xf "%ZIP%" -C "%DEST%" >nul 2>&1
exit /b 0
