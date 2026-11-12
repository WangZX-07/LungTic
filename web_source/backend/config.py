import os

_DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "lungtic-dev.sqlite").replace("\\", "/")
DATABASE_URL = os.getenv("LUNGTIC_DB_URL", f"sqlite:///{_DEFAULT_DB_PATH}")

JWT_SECRET = os.getenv("LUNGTIC_JWT_SECRET", "lungtic-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 480

UPLOAD_DIR = os.getenv(
    "LUNGTIC_DATA_DIR",
    os.path.join(os.path.dirname(__file__), "data"),
)
MODEL_DIR = os.path.join(UPLOAD_DIR, "models")
DICOM_DIR = os.path.join(UPLOAD_DIR, "dicom")
TICI_DIR = os.path.join(UPLOAD_DIR, "tici")
TICI_VIEWER_DIR = os.path.join(TICI_DIR, "viewer")
RECORD_DIR = os.path.join(UPLOAD_DIR, "records")
SERVER_MODE = os.getenv("LUNGTIC_SERVER_MODE") == "1"
CORS_ORIGINS = [origin.strip() for origin in os.getenv("LUNGTIC_CORS_ORIGINS", "http://127.0.0.1:5173").split(",") if origin.strip()]

os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(DICOM_DIR, exist_ok=True)
os.makedirs(TICI_DIR, exist_ok=True)
os.makedirs(TICI_VIEWER_DIR, exist_ok=True)
os.makedirs(RECORD_DIR, exist_ok=True)

# SMTP Email config
SMTP_HOST = os.getenv("LUNGTIC_SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.getenv("LUNGTIC_SMTP_PORT", "465"))
SMTP_USERNAME = os.getenv("LUNGTIC_SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("LUNGTIC_SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("LUNGTIC_SMTP_FROM", SMTP_USERNAME)

# Captcha config
CAPTCHA_SECRET = os.getenv("LUNGTIC_CAPTCHA_SECRET", "lungtic-captcha-secret")
CAPTCHA_EXPIRE_SECONDS = 300
CAPTCHA_TOLERANCE = 5

# Standalone project progress portal.  Values are injected on the server and
# must never be compiled into the browser bundle.
PROJECT_ORIGIN = os.getenv("LUNGTIC_PROJECT_ORIGIN", "http://127.0.0.1:5175").rstrip("/")
PROJECT_COOKIE_SECURE = os.getenv(
    "LUNGTIC_PROJECT_COOKIE_SECURE",
    "1" if PROJECT_ORIGIN.startswith("https://") else "0",
) == "1"
FEISHU_APP_ID = os.getenv("LUNGTIC_FEISHU_APP_ID", "").strip()
FEISHU_APP_SECRET = os.getenv("LUNGTIC_FEISHU_APP_SECRET", "").strip()
FEISHU_REDIRECT_URI = os.getenv(
    "LUNGTIC_FEISHU_REDIRECT_URI",
    PROJECT_ORIGIN + "/api/project/auth/callback",
).strip()
PROJECT_BOOTSTRAP_OPEN_IDS = {
    value.strip() for value in os.getenv("LUNGTIC_PROJECT_BOOTSTRAP_OPEN_IDS", "").split(",") if value.strip()
}
GITHUB_WEBHOOK_SECRET = os.getenv("LUNGTIC_GITHUB_WEBHOOK_SECRET", "").strip()
GITHUB_REPOSITORY = os.getenv("LUNGTIC_GITHUB_REPOSITORY", "WangZX-07/LungTic").strip()
GITHUB_API_TOKEN = os.getenv("LUNGTIC_GITHUB_API_TOKEN", "").strip()
