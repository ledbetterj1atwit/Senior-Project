@echo OFF
if %scriptb%==--script nmap %para% %scriptb% %script% %ip%> out.txt
if %scriptb%==0 nmap %para%  %ip% > scan_log\out.txt
pause