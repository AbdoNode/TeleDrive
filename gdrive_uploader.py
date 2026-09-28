import os
import mimetypes
from typing import Dict, List, Optional
from tqdm import tqdm
import logging

# إخفاء تحذيرات Google Cloud
logging.getLogger('google.auth._default').setLevel(logging.ERROR)
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
os.environ['GOOGLE_CLOUD_PROJECT'] = 'dummy-project'
import warnings
warnings.filterwarnings("ignore", message="No project ID could be determined")
warnings.filterwarnings("ignore", message="file_cache is only supported with oauth2client")

from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

from config import get_logger

logger = get_logger(__name__)

# إخفاء رسائل INFO لتقليل كمية المخرجات
logger.setLevel(logging.WARNING)

# التحقق مما إذا كان التشغيل داخل Google Colab
try:
    from google.colab import auth
    from googleapiclient.discovery import build
    IN_COLAB = True
    logger.info("يعمل حاليًا في بيئة Google Colab")
except ImportError:
    IN_COLAB = False
    logger.warning("لا يعمل في Google Colab - ميزات الرفع غير متاحة")


def get_drive_service():
    """
    الحصول على خدمة Google Drive بعد المصادقة.

    Returns:
        كائن خدمة Google Drive

    Raises:
        RuntimeError: إذا لم يكن التشغيل داخل Colab أو فشلت المصادقة
    """
    if not IN_COLAB:
        raise RuntimeError("لا يعمل في بيئة Google Colab")

    try:
        # إخفاء التحذيرات أثناء المصادقة
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            # إجراء المصادقة وإنشاء الخدمة مباشرة
            auth.authenticate_user()
            drive_service = build('drive', 'v3')
            return drive_service

    except Exception as e:
        raise RuntimeError(f"فشلت المصادقة مع Google Drive: {str(e)}")


def get_or_create_TeleDrive_folder(drive_service) -> Optional[str]:
    """
    الحصول على مجلد 'Torrent Downloads' أو إنشاؤه
    في المجلد الرئيسي لـ Google Drive.

    Args:
        drive_service: كائن خدمة Google Drive بعد المصادقة

    Returns:
        معرّف مجلد Torrent Downloads، أو None إذا فشلت العملية
    """
    try:
        # البحث عن مجلد Torrent Downloads الموجود في المجلد الرئيسي
        query = "name='Torrent Downloads' and mimeType='application/vnd.google-apps.folder' and trashed=false and 'root' in parents"

        results = drive_service.files().list(
            q=query,
            fields='files(id, name)',
            pageSize=1
        ).execute()

        folders = results.get('files', [])

        if folders:
            logger.info(
                f"تم العثور على مجلد Torrent Downloads موجود بالفعل: {folders[0]['id']}"
            )
            return folders[0]['id']

        # إنشاء مجلد Torrent Downloads جديد إذا لم يتم العثور عليه
        folder_metadata = {
            'name': 'Torrent Downloads',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        folder = drive_service.files().create(
            body=folder_metadata,
            fields='id'
        ).execute()

        folder_id = folder.get('id')

        logger.info(
            f"تم إنشاء مجلد Torrent Downloads جديد: {folder_id}"
        )

        return folder_id

    except HttpError as e:
        logger.error(
            f"حدث خطأ أثناء الحصول على مجلد Torrent Downloads أو إنشائه: {str(e)}"
        )
        return None

    except Exception as e:
        logger.error(
            f"حدث خطأ غير متوقع أثناء الحصول على مجلد Torrent Downloads أو إنشائه: {str(e)}"
        )
        return None


# للتوافق مع الإصدارات السابقة - تم الاحتفاظ بهذه الدالة للكود القديم
def set_drive_service(service):
    """دالة قديمة - لم تعد مطلوبة مع المصادقة التلقائية."""
    logger.info("تم تعيين خدمة Drive باستخدام المصادقة التلقائية")


class SimpleDriveUploader:
    """رافع مبسط إلى Google Drive مع شريط تقدم وخاصية تخطي الملفات الموجودة بالفعل."""

    def __init__(
        self,
        skip_existing: bool = True,
        use_TeleDrive_folder: bool = True
    ):
        """
        تهيئة الرافع مع المصادقة التلقائية.

        Args:
            skip_existing:
                إذا كانت True، يتم تخطي الملفات الموجودة بالفعل في Drive.

            use_TeleDrive_folder:
                إذا كانت True، يتم إنشاء/استخدام مجلد
                Torrent Downloads تلقائيًا في المجلد الرئيسي لـ Drive.

        Raises:
            RuntimeError:
                إذا لم يكن التشغيل داخل Colab أو فشلت المصادقة.
        """

        self.drive_service = get_drive_service()
        self.skip_existing = skip_existing
        self.use_TeleDrive_folder = use_TeleDrive_folder
        self.TeleDrive_folder_id = None

        # الحصول على مجلد Torrent Downloads أو إنشاؤه إذا كان الخيار مفعّلًا
        if self.use_TeleDrive_folder:
            self.TeleDrive_folder_id = get_or_create_TeleDrive_folder(
                self.drive_service
            )

            if not self.TeleDrive_folder_id:
                raise RuntimeError(
                    "فشل إنشاء أو الوصول إلى مجلد Torrent Downloads في Google Drive"
                )

    def file_exists(
        self,
        file_name: str,
        parent_id: str
    ) -> Optional[Dict]:
        """
        التحقق مما إذا كان هناك ملف بالاسم المحدد
        موجود بالفعل داخل المجلد الأب.

        Args:
            file_name:
                اسم الملف المطلوب التحقق منه.

            parent_id:
                معرّف المجلد الأب.

        Returns:
            معلومات الملف إذا كان موجودًا، وإلا None.
        """

        try:
            # معالجة علامات الاقتباس المفردة في اسم الملف لاستخدامها في البحث
            escaped_name = file_name.replace("'", "\\'")

            query = (
                f"name='{escaped_name}' and "
                f"'{parent_id}' in parents and trashed=false"
            )

            results = self.drive_service.files().list(
                q=query,
                fields='files(id, name, size, mimeType)',
                pageSize=1
            ).execute()

            files = results.get('files', [])

            if files:
                return files[0]

            return None

        except HttpError as e:
            logger.error(
                f"حدث خطأ أثناء التحقق من وجود الملف: {str(e)}"
            )
            return None

    def folder_exists(
        self,
        folder_name: str,
        parent_id: str
    ) -> Optional[str]:
        """
        التحقق مما إذا كان هناك مجلد بالاسم المحدد
        موجود بالفعل داخل المجلد الأب.

        Args:
            folder_name:
                اسم المجلد المطلوب التحقق منه.

            parent_id:
                معرّف المجلد الأب.

        Returns:
            معرّف المجلد إذا كان موجودًا، وإلا None.
        """

        try:
            # معالجة علامات الاقتباس المفردة في اسم المجلد لاستخدامها في البحث
            escaped_name = folder_name.replace("'", "\\'")

            query = (
                f"name='{escaped_name}' and "
                f"'{parent_id}' in parents "
                f"and mimeType='application/vnd.google-apps.folder' "
                f"and trashed=false"
            )

            results = self.drive_service.files().list(
                q=query,
                fields='files(id, name)',
                pageSize=1
            ).execute()

            folders = results.get('files', [])

            if folders:
                return folders[0]['id']

            return None

        except HttpError as e:
            logger.error(
                f"حدث خطأ أثناء التحقق من وجود المجلد: {str(e)}"
            )
            return None

    def upload_file(
        self,
        local_path: str,
        parent_id: str
    ) -> Optional[str]:
        """
        رفع ملف واحد إلى Google Drive مع شريط تقدم.

        Args:
            local_path:
                مسار الملف الموجود محليًا.

            parent_id:
                معرّف مجلد Google Drive الذي سيتم رفع الملف إليه.

        Returns:
            معرّف الملف إذا نجح الرفع، وإلا None.
        """

        file_name = os.path.basename(local_path)

        # التحقق مما إذا كان الملف موجودًا بالفعل
        if self.skip_existing:
            existing = self.file_exists(
                file_name,
                parent_id
            )

            if existing:
                return existing['id']

        # تحديد نوع MIME للملف
        mime_type, _ = mimetypes.guess_type(local_path)

        if not mime_type:
            mime_type = 'application/octet-stream'

        # تجهيز بيانات الملف
        file_metadata = {
            'name': file_name,
            'parents': [parent_id]
        }

        try:
            # إنشاء عملية رفع قابلة للاستكمال
            media = MediaFileUpload(
                local_path,
                mimetype=mime_type,
                resumable=True
            )

            request = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            )

            # رفع الملف بدون شريط تقدم منفصل لكل ملف
            response = None

            while response is None:
                status, response = request.next_chunk()

            file_id = response.get('id')

            return file_id

        except HttpError as e:
            logger.error(
                f"خطأ HTTP أثناء رفع '{file_name}': {str(e)}"
            )
            return None

        except Exception as e:
            logger.error(
                f"خطأ غير متوقع أثناء رفع '{file_name}': {str(e)}"
            )
            return None

    def create_folder(
        self,
        folder_name: str,
        parent_id: str
    ) -> Optional[str]:
        """
        إنشاء مجلد في Google Drive
        أو إرجاع معرّف المجلد الموجود بالفعل.

        Args:
            folder_name:
                اسم المجلد المطلوب إنشاؤه.

            parent_id:
                معرّف المجلد الأب.

        Returns:
            معرّف المجلد إذا نجحت العملية، وإلا None.
        """

        # التحقق مما إذا كان المجلد موجودًا بالفعل
        if self.skip_existing:
            existing_id = self.folder_exists(
                folder_name,
                parent_id
            )

            if existing_id:
                return existing_id

        try:
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }

            folder = self.drive_service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()

            folder_id = folder.get('id')

            return folder_id

        except Exception as e:
            logger.error(
                f"خطأ أثناء إنشاء المجلد '{folder_name}': {str(e)}"
            )
            return None

    def count_items(
        self,
        local_path: str
    ) -> Dict[str, int]:
        """
        حساب إجمالي عدد الملفات والمجلدات
        والحجم الإجمالي في المسار.

        Args:
            local_path:
                المسار الذي سيتم حساب محتوياته.

        Returns:
            قاموس يحتوي على عدد الملفات والمجلدات والحجم الإجمالي.
        """

        if os.path.isfile(local_path):
            return {
                'files': 1,
                'folders': 0,
                'total_size': os.path.getsize(local_path)
            }

        files = 0
        folders = 0
        total_size = 0

        try:
            for root, dirs, filenames in os.walk(local_path):
                folders += len(dirs)
                files += len(filenames)

                for filename in filenames:
                    try:
                        file_path = os.path.join(
                            root,
                            filename
                        )

                        total_size += os.path.getsize(
                            file_path
                        )

                    except OSError:
                        pass

        except Exception as e:
            logger.error(
                f"خطأ أثناء حساب العناصر: {str(e)}"
            )

        return {
            'files': files,
            'folders': folders,
            'total_size': total_size
        }

    def upload_to_drive(
        self,
        local_path: str,
        parent_id: str,
        _progress_bar=None,
        _total_size=None,
        _uploaded_size=[0],
        _file_count=[0, 0]  # [الملف الحالي، إجمالي الملفات]
    ) -> Dict[str, any]:
        """
        رفع ملف أو مجلد إلى Google Drive بشكل متكرر.

        Args:
            local_path:
                مسار الملف أو المجلد الموجود محليًا.

            parent_id:
                معرّف مجلد Google Drive الذي سيتم رفع المحتوى إليه.
                سيتم استخدامه كمجلد فرعي داخل Torrent Downloads
                إذا كان use_TeleDrive_folder مفعّلًا.

        Returns:
            قاموس يحتوي على قوائم الملفات الناجحة
            والفاشلة والمتخطاة بالإضافة إلى root_folder_id.
        """

        results = {
            'success': [],
            'failed': [],
            'skipped': [],
            'root_folder_id': parent_id
        }

        # التحقق من صحة المسار
        if not os.path.exists(local_path):
            results['failed'].append(local_path)
            return results

        # تهيئة تتبع التقدم عند أول استدعاء للدالة
        if _progress_bar is None:
            stats = self.count_items(local_path)

            _total_size = stats['total_size']
            _file_count[1] = stats['files']
            _uploaded_size[0] = 0
            _file_count[0] = 0

            size_mb = _total_size / (1024 * 1024)

            print(
                f"📤 جاري رفع {stats['files']} ملف "
                f"({size_mb:.1f} MB)"
            )

            _progress_bar = tqdm(
                total=_total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                desc="الرفع",
                bar_format=(
                    "{desc}: {percentage:3.0f}%|{bar}| "
                    "{n_fmt}/{total_fmt} "
                    "[{rate_fmt}] {postfix}"
                ),
                disable=False,
                leave=True,
                ncols=100
            )

        # رفع ملف
        if os.path.isfile(local_path):
            file_name = os.path.basename(local_path)
            file_size = os.path.getsize(local_path)

            existing = (
                self.file_exists(file_name, parent_id)
                if self.skip_existing
                else None
            )

            if existing:
                results['skipped'].append(local_path)

                # تحديث شريط التقدم حتى في حالة تخطي الملف
                if _progress_bar:
                    _uploaded_size[0] += file_size
                    _file_count[0] += 1

                    _progress_bar.set_postfix_str(
                        f"Files: {_file_count[0]}/{_file_count[1]}"
                    )

                    _progress_bar.update(file_size)

            else:
                file_id = self.upload_file(
                    local_path,
                    parent_id
                )

                if file_id:
                    results['success'].append(local_path)
                else:
                    results['failed'].append(local_path)

                # تحديث شريط التقدم بعد رفع الملف
                if _progress_bar:
                    _uploaded_size[0] += file_size
                    _file_count[0] += 1

                    _progress_bar.set_postfix_str(
                        f"Files: {_file_count[0]}/{_file_count[1]}"
                    )

                    _progress_bar.update(file_size)

            return results

        # رفع مجلد
        if os.path.isdir(local_path):
            folder_name = os.path.basename(local_path)

            folder_id = self.create_folder(
                folder_name,
                parent_id
            )

            if folder_id:
                # حفظ معرّف المجلد الذي تم إنشاؤه كمجلد رئيسي لعملية الرفع
                results['root_folder_id'] = folder_id

                # رفع جميع العناصر الموجودة داخل المجلد بشكل متكرر
                try:
                    for item in os.listdir(local_path):
                        item_path = os.path.join(
                            local_path,
                            item
                        )

                        sub_results = self.upload_to_drive(
                            item_path,
                            folder_id,
                            _progress_bar,
                            _total_size,
                            _uploaded_size,
                            _file_count
                        )

                        results['success'].extend(
                            sub_results['success']
                        )

                        results['failed'].extend(
                            sub_results['failed']
                        )

                        results['skipped'].extend(
                            sub_results['skipped']
                        )

                except Exception as e:
                    results['failed'].append(local_path)

            else:
                results['failed'].append(local_path)

            # إغلاق شريط التقدم عند انتهاء عملية الرفع
            if (
                _progress_bar
                and _file_count[0] >= _file_count[1]
            ):
                _progress_bar.close()
                print()

            return results

        # إغلاق شريط التقدم عند انتهاء عملية الرفع
        if (
            _progress_bar
            and _file_count[0] >= _file_count[1]
        ):
            _progress_bar.close()
            print()

        results['failed'].append(local_path)

        return results

    def print_summary(
        self,
        results: Dict[str, List[str]],
        root_folder_id: str = None
    ):
        """طباعة ملخص الرفع مع رابط المجلد."""

        print("\n" + "=" * 60)
        print("🎉 اكتمل الرفع")
        print("=" * 60)

        total_files = (
            len(results['success'])
            + len(results.get('skipped', []))
        )

        print(
            f"✅ تم رفع {len(results['success'])} ملف بنجاح"
        )

        if results.get('skipped'):
            print(
                f"⏭️  تم تخطي {len(results['skipped'])} ملف "
                f"(موجود بالفعل)"
            )

        if results['failed']:
            print(
                f"❌ فشل رفع {len(results['failed'])} ملف"
            )

        if root_folder_id:
            folder_url = (
                f"https://drive.google.com/drive/folders/"
                f"{root_folder_id}"
            )

            print(
                f"\n📁 عرض الملفات التي تم رفعها: {folder_url}"
            )

        print("=" * 60)


def upload_to_google_drive(
    local_path: str,
    folder_id: str = None,
    **kwargs
):
    """
    رفع الملفات إلى Google Drive مع المصادقة التلقائية.

    يتم إنشاء/استخدام مجلد 'Torrent Downloads'
    تلقائيًا في المجلد الرئيسي لـ Google Drive.

    Args:
        local_path:
            مسار الملف أو المجلد المطلوب رفعه.

        folder_id:
            معرّف مجلد Google Drive المستهدف (اختياري).
            ويستخدم مجلد Torrent Downloads افتراضيًا.

        **kwargs:
            خيارات إضافية:

            - skip_existing (bool):
              تخطي الملفات الموجودة بالفعل.
              القيمة الافتراضية: True

            - use_TeleDrive_folder (bool):
              استخدام مجلد Torrent Downloads
              في المجلد الرئيسي لـ Drive.
              القيمة الافتراضية: True

    Returns:
        قاموس يحتوي على قوائم الملفات الناجحة
        والفاشلة والمتخطاة.

    Raises:
        RuntimeError:
            إذا لم يكن التشغيل داخل Colab أو فشلت المصادقة.
    """

    skip_existing = kwargs.get(
        'skip_existing',
        True
    )

    use_TeleDrive_folder = (
        folder_id is None
    )

    uploader = SimpleDriveUploader(
        skip_existing=skip_existing,
        use_TeleDrive_folder=use_TeleDrive_folder
    )

    # تحديد وجهة الرفع: المجلد المخصص له الأولوية
    if folder_id is None:
        folder_id = (
            uploader.TeleDrive_folder_id
            if use_TeleDrive_folder
            else 'root'
        )

    results = uploader.upload_to_drive(
        local_path,
        folder_id
    )

    root_folder_id = results.get(
        'root_folder_id',
        folder_id
    )

    uploader.print_summary(
        results,
        root_folder_id
    )

    return results