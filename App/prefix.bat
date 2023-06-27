@echo off
rem save vars to ignore
set > iv
rem import new vars
for /f "tokens=*" %%a in (nv) do call :importv %%a
del nv
goto :attack

:importv
set %*
goto :eof

:attack
