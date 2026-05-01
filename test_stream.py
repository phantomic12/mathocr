#!/usr/bin/env python3
import http.client, json, base64, time

conn = http.client.HTTPConnection("localhost", 8000)

def api(method, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    b = json.dumps(body).encode() if body is not None else None
    conn.request(method, path, body=b, headers=headers)
    return json.loads(conn.getresponse().read().decode())

# Login
resp = api("POST", "/api/auth/login", {"email": "yoav@test.com", "password": "test1234"})
token = resp["access_token"]
print("Logged in")

# Upload
boundary = "----MathOCRBoundary"
with open("/tmp/q.png", "rb") as f:
    img_bytes = f.read()
body_parts = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="file"; filename="q.png"\r\n'
    f"Content-Type: image/png\r\n\r\n"
).encode() + img_bytes + f"\r\n--{boundary}--\r\n".encode()

conn.request("POST", "/api/ocr/upload", body=body_parts, headers={
    "Authorization": "Bearer " + token,
    "Content-Type": "multipart/form-data; boundary=" + boundary,
})
resp = json.loads(conn.getresponse().read().decode())
jid = resp["job_id"]
print("Job:", jid)

# Poll status
for i in range(20):
    time.sleep(1)
    s = api("GET", "/api/ocr/status/" + jid, token=token)
    pt = s.get("process_time_ms") or "?"
    latex_len = len(s.get("latex") or "")
    print(f"{i+1}s: status={s['status']}  time={pt}ms  latex_len={latex_len}")
    if s["status"] in ("done", "error"):
        print("LaTeX:", s.get("latex", "")[:100])
        break
