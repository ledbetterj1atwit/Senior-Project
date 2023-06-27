
rem save current vars
set > cv

rem remove ignored vars
diff.exe -n iv cv > dv

set other=1

for /f "tokens=*" %%a in (dv) do call :exportv %%a

goto :cleanup

:exportv
if [%other%]==[1] (
  set other=
  goto :eof
)
echo %* >> nv
set other=1
goto :eof

:cleanup
del iv
del dv
del cv

:eof