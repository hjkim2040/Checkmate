import os

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

EMBEDDING_REPO_ID = os.environ.get("EMBEDDING_REPO_ID")

QDRANT_URL = os.environ.get("QDRANT_URL")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY")

MONGO_HOST = os.environ.get("MONGO_HOST", "localhost")
MONGO_PORT = os.environ.get("MONGO_PORT", "27017")
MONGO_DB = os.environ.get("MONGO_DB")
MONGO_USERNAME = os.environ.get("MONGO_USERNAME")
MONGO_PASSWORD = os.environ.get("MONGO_PASSWORD")
MONGO_AUTH = os.environ.get("MONGO_AUTH")


# MongoDB URI 구성
if MONGO_USERNAME and MONGO_PASSWORD:
    # URL 인코딩 처리
    from urllib.parse import quote_plus

    username = quote_plus(MONGO_USERNAME)
    password = quote_plus(MONGO_PASSWORD)
    MONGO_URI = f"mongodb://{username}:{password}@{MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}?authSource={MONGO_AUTH}"
else:
    MONGO_URI = f"mongodb://{MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}"

AI_ANALYSIS_REPORT_COLLECTION = os.environ.get("AI_ANALYSIS_REPORT_COLLECTION")
IMPROVEMENT_REPORT_COLLECTION = os.environ.get("IMPROVEMENT_REPORT_COLLECTION")
MISSING_CLAUSE_REPORT_COLLECTION = os.environ.get("MISSING_CLAUSE_REPORT_COLLECTION")
RISK_CLAUSE_REPORT_COLLECTION = os.environ.get("RISK_CLAUSE_REPORT_COLLECTION")

MYSQL_HOST = os.environ.get("MYSQL_HOST")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT"))
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE")
MYSQL_USERNAME = os.environ.get("MYSQL_USERNAME")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD")

REDIS_HOST = os.environ.get("REDIS_HOST")
REDIS_PORT = os.environ.get("REDIS_PORT")
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")
OCR_CACHE_TTL = int(os.environ.get("OCR_CACHE_TTL", 3600))

# AWS S3
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# Upstage OCR
UPSTAGE_OCR_API_URL = os.getenv("UPSTAGE_OCR_API_URL")
UPSTAGE_OCR_API_KEY = os.getenv("UPSTAGE_OCR_API_KEY")

# Encryption
ENCRYPTION_BASE64_KEY = os.getenv("ENCRYPTION_BASE64_KEY")

SPRINGBOOT_WEBHOOK_URL = os.getenv("SPRINGBOOT_WEBHOOK_URL")
WEBHOOK_API_KEY = os.getenv("WEBHOOK_API_KEY")

HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
