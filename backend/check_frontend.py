"""Serve production frontend, check 4 routes return 200. Run from repo root."""
import subprocess, time, urllib.request, sys

p = subprocess.Popen("npm run start -- -p 3001", cwd=r"D:\Builds\paypal-hackathon\frontend",
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
try:
    time.sleep(16)
    for u in ["/", "/login", "/agreements/new", "/assistant"]:
        print(u, urllib.request.urlopen("http://127.0.0.1:3001" + u, timeout=20).status)
finally:
    p.terminate()
print("FRONTEND_ROUTES_OK")
