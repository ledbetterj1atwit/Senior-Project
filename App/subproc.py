import subprocess

command_out = subprocess.run([r"C:\Program Files (x86)\Nmap\nmap.exe", "-v", "-A", "scanme.nmap.org"], shell=True, capture_output=True)
print(command_out.stdout.decode("windows-1250"))
