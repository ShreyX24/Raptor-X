# SSH Automation for SUTs

## Status: Pending

## Problem
SSH key-based authentication needs to be set up for passwordless access to SUTs, enabling automated deployment.

## Current State
- SSH key generated on dev machine: `~/.ssh/id_rsa_sut`
- Public key added to ZEL-X7's `C:\ProgramData\ssh\administrators_authorized_keys`
- sshd service fails to start (error 1332 - SID mapping issue)

## Fix Steps (To Do on ZEL-X7)

```powershell
# Option 1: Reset service account
sc.exe config sshd obj= "LocalSystem"
Start-Service sshd

# Option 2: If Option 1 fails, re-register the service
sc.exe delete sshd
sc.exe create sshd binPath= "C:\Windows\System32\OpenSSH\sshd.exe" start= auto
sc.exe config sshd obj= "LocalSystem"
Start-Service sshd
```

## Once Fixed

From dev machine:
```bash
# Test connection
ssh -i ~/.ssh/id_rsa_sut zelos@192.168.0.106 "echo connected"

# Deploy SUT client
scp -i ~/.ssh/id_rsa_sut dist/pml_sut_client-*.whl zelos@192.168.0.106:~/
ssh -i ~/.ssh/id_rsa_sut zelos@192.168.0.106 "pip install ~/pml_sut_client-*.whl --force-reinstall"
```

## Benefits When Complete
- One-command SUT client deployment
- Automated SUT management from orchestrator
- Remote log collection
