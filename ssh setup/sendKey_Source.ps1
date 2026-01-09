# 1. Generate SSH Key if it doesn't exist
if (-not (Test-Path "$env:USERPROFILE\.ssh\id_ed25519")) {
    ssh-keygen -t ed25519 -N "" -f "$env:USERPROFILE\.ssh\id_ed25519"
}

# 2. Extract Public Key
$pubKey = Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub"

# 3. Output the Final Command to run on the Target PC
Write-Host "`n--- COPY THE LINE BELOW AND RUN IT ON THE TARGET PC (ADMIN PS) ---`n" -ForegroundColor Yellow
Write-Host "Set-Content -Path 'C:\ProgramData\ssh\administrators_authorized_keys' -Value '$pubKey'; icacls.exe 'C:\ProgramData\ssh\administrators_authorized_keys' /inheritance:r /grant 'Administrators:F' /grant 'SYSTEM:F'; Restart-Service sshd"
Write-Host "`n--- END OF COMMAND ---`n"
