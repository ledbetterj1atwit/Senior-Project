@echo OFF
if %scriptb%==--script nmap %para% %scriptb% %script% %ip%> out.txt
if %scriptb%==0 nmap %para%  %ip% > out.txt
pause