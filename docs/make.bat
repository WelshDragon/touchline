@ECHO OFF

set SPHINXBUILD=sphinx-build
set SOURCEDIR=.
set BUILDDIR=_build

if "%1"=="" goto help

%SPHINXBUILD% -b %1 %SOURCEDIR% %BUILDDIR%\%1 %SPHINXOPTS%
if errorlevel 1 exit /b 1

goto end

:help
%SPHINXBUILD% -b help %SOURCEDIR% %BUILDDIR%\help %SPHINXOPTS%

:end
ECHO.
ECHO Build finished. The HTML pages are in %BUILDDIR%\html.
