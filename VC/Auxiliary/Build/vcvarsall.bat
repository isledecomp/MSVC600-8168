@echo off

set __VCVARSALL_TARGET_ARCH=
set "__VCVARSALL_ARGS_LIST=%*"

call :parse_loop

if "%__VCVARSALL_TARGET_ARCH%" == "" (
    goto :usage_error
)

set __MSVC_ROOT=%~dp0..\..\..
for %%i in ("%__MSVC_ROOT%") do SET "__MSVC_ROOT=%%~fi"

@echo [vcvarsall.bat] Environment initialized for: 'x86'

set PATH=%__MSVC_ROOT%\VC98\Bin;%PATH%
set INCLUDE=%__MSVC_ROOT%\VC98\Include;%__MSVC_ROOT%\VC98\ATL\Include;%__MSVC_ROOT%\VC98\MFC\Include;%INCLUDE%
set LIB=%__MSVC_ROOT%\VC98\Lib;%__MSVC_ROOT%\VC98\MFC\Lib;%LIB%
set VisualStudioVersion=6.00


:parse_loop
for /F "tokens=1,* delims= " %%a in ("%__VCVARSALL_ARGS_LIST%") do (
    call :parse_argument %%a
    set "__VCVARSALL_ARGS_LIST=%%b"
    goto :parse_loop
)

exit /B 0

:parse_argument

set __local_ARG_FOUND=
if /I "%1"=="x86" (
    set __VCVARSALL_TARGET_ARCH=x86
    set __local_ARG_FOUND=1
)
@REM  CLion requires amd64 support, so fake it
if /I "%1"=="amd64" (
   set __VCVARSALL_TARGET_ARCH=amd64
   set __local_ARG_FOUND=1
)
if "%__local_ARG_FOUND%" NEQ "1" (
    if "%2"=="" (
        @echo [ERROR:%~nx0] Invalid argument found : %1
    ) else (
        @echo [ERROR:%~nx0] Invalid argument found : %1=%2
    )
)
set __local_ARG_FOUND=
exit /B 0

:usage_error

echo [ERROR:%~nx0] Error in script usage.

:end
set __VCVARSALL_TARGET_ARCH=
set __VCVARSALL_ARGS_LIST=
set __MSVC_ROOT=
