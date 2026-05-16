@echo off
setlocal EnableDelayedExpansion

set "ARGS="

:next_arg
if "%~1"=="" goto run_codex
set "ARG=%~1"
set "ARG=!ARG:'=!"
set "ARGS=!ARGS! "!ARG!""
shift
goto next_arg

:run_codex
call "%APPDATA%\npm\codex.cmd" %ARGS%
exit /b %ERRORLEVEL%
