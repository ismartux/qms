import requests

# --------------------------------------------------
# CONFIG (EDIT THESE)
# --------------------------------------------------

BASE_URL = "http://127.0.0.1:8000/"
LOGIN_URL = f"{BASE_URL}/admin/login/"
SYNC_URL = f"{BASE_URL}/api/jobs/bitable-sync/"

USERNAME = "test123"          # 👈 your admin username
PASSWORD = "Vikram@0729"       # 👈 your admin password

# --------------------------------------------------
# SCRIPT
# --------------------------------------------------

session = requests.Session()

# 1️⃣ Get CSRF token
login_page = session.get(LOGIN_URL)
login_page.raise_for_status()

csrftoken = session.cookies.get("csrftoken")
if not csrftoken:
    raise RuntimeError("CSRF token not found")

# 2️⃣ Login
login_response = session.post(
    LOGIN_URL,
    data={
        "username": USERNAME,
        "password": PASSWORD,
        "csrfmiddlewaretoken": csrftoken,
        "next": "/admin/",
    },
    headers={"Referer": LOGIN_URL},
)

if login_response.status_code != 200:
    raise RuntimeError("Login failed")

print("✅ Logged into production Django")

# 3️⃣ Trigger the job
response = session.post(SYNC_URL)
response.raise_for_status()

print("🚀 Bitable sync triggered successfully")
print(response.json())
