#!/usr/bin/env python3
import http.client, json, time

c = http.client.HTTPConnection("localhost", 8000)
c.request("POST", "/api/auth/login",
          body=json.dumps({"email": "yoav@test.com", "password": "test1234"}).encode(),
          headers={"Content-Type": "application/json"})
token = json.loads(c.getresponse().read().decode())["access_token"]
print("Token:", token[:20], "...")

# Upload via python http.client with correct multipart
BOUNDARY = "----MathOCRBoundary123"
with open("/tmp/q.png", "rb") as f:
    img_data = f.read()

body = (
    "--" + BOUNDARY + "\r\n"
    "Content-Disposition: form-data; name=\"file\"; filename=\"q.png\"\r\n"
    "Content-Type: image/png\r\n\r\n"
).encode() + img_data + ("\r\n--" + BOUNDARY + "--\r\n").encode()

c.request("POST", "/api/ocr/upload", body=body, headers={
    "Authorization": "Bearer " + token,
    "Content-Type": "multipart/form-data; boundary=" + BOUNDARY,
})
resp = json.loads(c.getresponse().read().decode())
print("Upload resp:", resp)
jid = resp.get("job_id") or resp.get("detail", "ERROR")
print("Job:", jid)

# Poll
for i in range(20):
    time.sleep(1)
    c.request("GET", "/api/ocr/status/" + jid, headers={"Authorization": "Bearer " + token})
    s = json.loads(c.getresponse().read().decode())
    print(f"{i+1}s: status={s['status']}  time={s.get('process_time_ms','?')}ms")
    if s["status"] in ("done", "error"):
        c.request("GET", "/api/ocr/result/" + jid, headers={"Authorization": "Bearer " + token})
        r2 = json.loads(c.getresponse().read().decode())
        print("LaTeX:", r2.get("latex", "")[:120])
        break
