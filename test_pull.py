"""Quick test: simulate what trace_puller does for PTAT on SUT 221"""
import subprocess
import os

SUT_IP = "192.168.50.221"
SSH_USER = "Administrator"
RUN_ID = "cf1d1750-813d-4d1d-a75c-a37413e381f8"
REMOTE_DIR = f"C:\\Traces\\{RUN_ID}"
PATTERN = "*_ptat_*.csv"

SSH_OPTS = [
    "-o", "BatchMode=yes",
    "-o", "StrictHostKeyChecking=no",
    "-o", "UserKnownHostsFile=/dev/null",
    "-o", "ConnectTimeout=10",
]

# Step 1: List files (same PowerShell command as trace_puller.list_remote_files)
cmd = f'powershell -Command "Get-ChildItem -Path \'{REMOTE_DIR}\' -Filter \'{PATTERN}\' -File -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name"'
print(f"=== Step 1: List files ===")
print(f"Remote dir: {REMOTE_DIR}")
print(f"Pattern: {PATTERN}")
print(f"SSH cmd: {cmd}")

result = subprocess.run(
    ["ssh"] + SSH_OPTS + [f"{SSH_USER}@{SUT_IP}", cmd],
    capture_output=True, text=True, timeout=30
)
print(f"returncode: {result.returncode}")
print(f"stdout: [{result.stdout.strip()}]")
if result.stderr:
    # Filter out known warnings
    for line in result.stderr.strip().split("\n"):
        if "WARNING" not in line and "Permanently added" not in line:
            print(f"stderr: {line}")

files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
print(f"Files found: {files}")

if not files:
    # Try broader pattern
    print("\n=== Trying broader pattern: *.csv ===")
    cmd2 = f'powershell -Command "Get-ChildItem -Path \'{REMOTE_DIR}\' -Filter \'*.csv\' -File -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name"'
    result2 = subprocess.run(
        ["ssh"] + SSH_OPTS + [f"{SSH_USER}@{SUT_IP}", cmd2],
        capture_output=True, text=True, timeout=30
    )
    print(f"stdout: [{result2.stdout.strip()}]")
    files = [f.strip() for f in result2.stdout.strip().split("\n") if f.strip()]

if files:
    filename = files[0]
    remote_path = f"{REMOTE_DIR}\\{filename}".replace("\\", "/")
    local_path = os.path.join(os.environ.get("TEMP", "/tmp"), "ptat_test_pull.csv")

    print(f"\n=== Step 2: SCP pull ===")
    print(f"Remote: {remote_path}")
    print(f"Local: {local_path}")

    scp_result = subprocess.run(
        ["scp"] + SSH_OPTS + [f"{SSH_USER}@{SUT_IP}:{remote_path}", local_path],
        capture_output=True, text=True, timeout=60
    )
    print(f"SCP returncode: {scp_result.returncode}")
    if scp_result.stderr:
        for line in scp_result.stderr.strip().split("\n"):
            if "WARNING" not in line and "Permanently added" not in line:
                print(f"SCP stderr: {line}")

    if os.path.exists(local_path):
        size = os.path.getsize(local_path)
        print(f"\nSUCCESS: Pulled {size:,} bytes to {local_path}")
    else:
        print("\nFAILED: File not created locally")
else:
    print("\nNo files found to pull!")
