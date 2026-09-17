import os

DATABASE_URL = os.getenv(
    "LUNGTIC_DB_URL",
    "mysql+pymysql://root:admin123@localhost:3306/lungtic"
)

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

os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(DICOM_DIR, exist_ok=True)
os.makedirs(TICI_DIR, exist_ok=True)
os.makedirs(TICI_VIEWER_DIR, exist_ok=True)

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
