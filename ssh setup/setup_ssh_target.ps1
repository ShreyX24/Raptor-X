# 1. Install OpenSSH Server
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0

# 2. Reset and Clean SSH Directory (Fixes common service start errors)
Remove-Item -Path "$env:ProgramData\ssh" -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path "$env:ProgramData\ssh" -Force

# 3. Start Service and Set to Automatic
Start-Service sshd
Set-Service -Name sshd -StartupType 'Automatic'

# 4. Open Firewall Port 22
New-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -DisplayName "OpenSSH Server (sshd)" -Enabled True -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow

# 5. Set Network Profile to Private (Required for local discovery)
Get-NetConnectionProfile | Set-NetConnectionProfile -NetworkCategory Private

Write-Host "SSH Server is Ready. Your IP is: $((Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike '*Loopback*'}).IPAddress)" -ForegroundColor Cyan
