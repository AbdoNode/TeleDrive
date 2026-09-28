import os
import json
import logging

# إعدادات مُنزّل التورنت
TORRENT_SESSION_FILE = "torrent_session.json"
TORRENT_DOWNLOAD_PATH = "../Torrent Downloads"

# إعدادات رافع الملفات إلى Google Drive
CHUNK_SIZE = 100 * 1024 * 1024  # أجزاء بحجم 100 ميجابايت للملفات الكبيرة
MAX_RETRIES = 3  # الحد الأقصى لإعادة المحاولة
RETRY_DELAY = 2  # مدة الانتظار الأساسية بالثواني قبل إعادة المحاولة مع التأخير المتزايد
LARGE_FILE_THRESHOLD = 1024 * 1024 * 1024  # الحد الذي يعتبر الملف بعده كبيرًا: 1 جيجابايت
MAX_WORKERS = 3  # عدد عمليات الرفع التي تعمل بالتوازي
PROGRESS_FILE = '.gdrive_upload_progress.json'  # ملف حفظ تقدم الرفع
CONFIG_FILE = '.gdrive-uploader.conf'  # ملف إعدادات رافع Google Drive
TOKEN_FILE = 'token.pickle'  # ملف رمز المصادقة
CREDENTIALS_FILE = 'credentials.dat'  # ملف بيانات الاعتماد
GOOGLE_DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.file']  # نطاق صلاحيات Google Drive

# إعدادات تسجيل الأحداث
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def get_logger(name):
    """الحصول على مسجّل الأحداث."""
    return logging.getLogger(name)


class ConfigManager:
    """إدارة ملف الإعدادات الخاص بحفظ الإعدادات الافتراضية."""
    
    @staticmethod
    def load_config(config_path: str = CONFIG_FILE) -> dict:
        """تحميل الإعدادات من الملف."""
        logger = get_logger(__name__)
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"تعذر تحميل ملف الإعدادات: {e}")
        return {}
    
    @staticmethod
    def save_config(config: dict, config_path: str = CONFIG_FILE):
        """حفظ الإعدادات في الملف."""
        logger = get_logger(__name__)
        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"تم حفظ الإعدادات في {config_path}")
        except Exception as e:
            logger.error(f"تعذر حفظ ملف الإعدادات: {e}")