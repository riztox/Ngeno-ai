"""Environment-backed configuration for NgenoAI."""
import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('NGENO_SECRET_KEY', 'change-this-secret-key')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_UPLOAD_MB', '16')) * 1024 * 1024
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-5.6')
    OPENAI_IMAGE_MODEL = os.getenv('OPENAI_IMAGE_MODEL', 'gpt-image-2.5-flare')
    DEMO_MODE = os.getenv('NGENO_DEMO_MODE', 'true').lower() == 'true'
