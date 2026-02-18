"""Deploy PTAT and PresentMon to C:\OWR on SUT via /file_upload endpoint."""
import os
import http.client
import json

SUT_IP = "192.168.50.221"
SUT_PORT = 8080
TOOLS_DIR = os.path.join(os.path.dirname(__file__), "tools")

AGENTS = {
    "ptat": r"C:\OWR\PTAT",
    "presentmon": r"C:\OWR\PresentMon",
}

def upload_file(filepath, dest_dir):
    """Upload a single file to SUT via multipart form."""
    filename = os.path.basename(filepath)
    boundary = "----RPXToolDeploy"

    with open(filepath, "rb") as f:
        file_data = f.read()

    # Build multipart body
    parts = []
    # path field
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"path\"\r\n\r\n{dest_dir}")
    # file field (binary)
    file_header = f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: application/octet-stream\r\n\r\n"
    footer = f"\r\n--{boundary}--\r\n"

    body = file_header.encode() + file_data + footer.encode()
    # Prepend the path part
    path_part = parts[0].encode() + b"\r\n"
    body = path_part + body

    conn = http.client.HTTPConnection(SUT_IP, SUT_PORT, timeout=60)
    conn.request("POST", "/file_upload", body=body,
                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    resp = conn.getresponse()
    result = json.loads(resp.read().decode())
    conn.close()
    return resp.status, result

total = 0
for agent_name, deploy_dir in AGENTS.items():
    local_dir = os.path.join(TOOLS_DIR, agent_name)
    if not os.path.isdir(local_dir):
        print(f"SKIP {agent_name}: {local_dir} not found")
        continue

    print(f"\nDeploying {agent_name} -> {deploy_dir}")
    for root, dirs, files in os.walk(local_dir):
        for fname in files:
            local_path = os.path.join(root, fname)
            rel = os.path.relpath(local_path, local_dir)
            rel_dir = os.path.dirname(rel)
            if rel_dir:
                dest = deploy_dir + "\\" + rel_dir.replace("/", "\\")
            else:
                dest = deploy_dir

            status, result = upload_file(local_path, dest)
            size = result.get("size", 0)
            ok = "OK" if result.get("success") else "FAIL"
            print(f"  {ok}  {rel} ({size:,} bytes)")
            if result.get("success"):
                total += 1

print(f"\nDone: {total} files deployed")
