#!/usr/bin/env python3

import sys
import argparse
import os
from pathlib import Path

from torrent_downloader import download_torrent, get_download_status, clear_session
from config import ConfigManager, TORRENT_DOWNLOAD_PATH, get_logger

logger = get_logger(__name__)


def get_uploader():
    """استيراد وإرجاع وحدة رفع الملفات."""
    try:
        from gdrive_uploader import upload_to_google_drive
        return upload_to_google_drive
    except ImportError as e:
        logger.error(f"فشل استيراد وحدة الرفع: {str(e)}")
        print("\n" + "="*60)
        print("خطأ: فشل استيراد وحدة رفع الملفات إلى Google Drive")
        print("="*60)
        print("تأكد من تثبيت جميع الحزم المطلوبة:")
        print("  pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        print("="*60)
        raise


def parse_arguments():
    """تحليل وسائط سطر الأوامر."""
    parser = argparse.ArgumentParser(
        description='تحميل ملفات Torrent ورفعها إلى Google Drive (محسّن لـ Colab)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
أمثلة:

  # تحميل ملف Torrent فقط
  python main.py download -t movie.torrent

  # استخدام رابط Magnet
  python main.py download -t "magnet:?xt=urn:btih:..."

  # تحميل ورفع الملف إلى Google Drive (Colab فقط)
  python main.py download -t movie.torrent --upload -f FOLDER_ID

  # رفع ملفات موجودة بالفعل إلى Google Drive (Colab فقط)
  python main.py upload -p /path/to/folder -f FOLDER_ID

  # رفع الملفات بدون تخطي الملفات الموجودة بالفعل
  python main.py upload -p /path -f FOLDER_ID --no-skip

  # التحقق من وجود عمليات تحميل متوقفة مؤقتًا
  python main.py status

  # مسح جلسة التحميل
  python main.py clear

ملاحظة:
ميزات الرفع تتعامل تلقائيًا مع المصادقة داخل Google Colab.
قم بتشغيل الأوامر مباشرة دون الحاجة إلى إعداد يدوي!
        """
    )

    subparsers = parser.add_subparsers(
        dest='command',
        help='الأمر المطلوب تنفيذه'
    )

    # أمر التحميل
    download_parser = subparsers.add_parser(
        'download',
        help='تحميل ملف Torrent'
    )

    download_parser.add_argument(
        '-t', '--torrent',
        type=str,
        required=True,
        help='مسار ملف Torrent أو رابط Magnet'
    )

    download_parser.add_argument(
        '-d', '--destination',
        type=str,
        default=TORRENT_DOWNLOAD_PATH,
        help=f'مكان حفظ الملفات (الافتراضي: {TORRENT_DOWNLOAD_PATH})'
    )

    download_parser.add_argument(
        '--no-resume',
        action='store_true',
        help='بدء تحميل جديد وتجاهل الجلسة السابقة'
    )

    download_parser.add_argument(
        '--upload',
        action='store_true',
        help='رفع الملفات إلى Google Drive بعد اكتمال التحميل (Colab فقط)'
    )

    download_parser.add_argument(
        '-f', '--folder-id',
        type=str,
        help='معرّف مجلد Google Drive (اختياري، والافتراضي هو مجلد Torrent Downloads في المجلد الرئيسي)'
    )

    download_parser.add_argument(
        '--no-skip',
        action='store_true',
        help='إعادة رفع الملفات حتى إذا كانت موجودة بالفعل في Google Drive'
    )

    # أمر الرفع
    upload_parser = subparsers.add_parser(
        'upload',
        help='رفع الملفات إلى Google Drive (Colab فقط)'
    )

    upload_parser.add_argument(
        '-p', '--path',
        type=str,
        required=True,
        help='المسار المحلي للملف أو المجلد المطلوب رفعه'
    )

    upload_parser.add_argument(
        '-f', '--folder-id',
        type=str,
        help='معرّف مجلد Google Drive المستهدف (اختياري، والافتراضي هو مجلد Torrent Downloads في المجلد الرئيسي)'
    )

    upload_parser.add_argument(
        '--no-skip',
        action='store_true',
        help='إعادة رفع الملفات حتى إذا كانت موجودة بالفعل في Google Drive'
    )

    # أمر عرض الحالة
    subparsers.add_parser(
        'status',
        help='التحقق من حالة التحميل'
    )

    # أمر المسح
    subparsers.add_parser(
        'clear',
        help='مسح جلسة التحميل'
    )

    return parser.parse_args()


def handle_download(args):
    """تنفيذ أمر تحميل ملف Torrent."""

    print("="*60)
    print("محمل ملفات TORRENT")
    print("="*60)

    # بدء تحميل ملف Torrent
    logger.info(f"بدء التحميل: {args.torrent}")

    downloaded_path = download_torrent(
        args.torrent,
        download_path=args.destination,
        auto_resume=not args.no_resume
    )

    if not downloaded_path:
        logger.error("فشل التحميل أو تم إلغاؤه")
        return 1

    logger.info(f"اكتمل التحميل: {downloaded_path}")

    # رفع الملفات إلى Google Drive إذا تم طلب ذلك
    if args.upload:
        print("\n" + "="*60)
        print("جاري الرفع إلى GOOGLE DRIVE")
        print("="*60)

        try:
            # تحميل وحدة الرفع
            upload_to_google_drive = get_uploader()

            results = upload_to_google_drive(
                downloaded_path,
                args.folder_id,
                skip_existing=not args.no_skip
            )

            if results['failed']:
                logger.warning(
                    f"فشل رفع بعض الملفات "
                    f"({len(results['failed'])} عنصر)"
                )
                return 1

            logger.info("اكتمل الرفع بنجاح!")

        except RuntimeError as e:
            # التعامل مع أخطاء البيئة أو التهيئة برسالة منسقة
            error_str = str(e)

            if error_str.startswith('\n'):
                # الرسالة منسقة بالفعل، لذلك يتم طباعتها مباشرة
                print(error_str)
            else:
                # إضافة تنسيق للرسالة
                print("\n" + "="*60)
                print("خطأ أثناء الرفع")
                print("="*60)
                print(error_str)
                print("="*60)

            return 1

        except Exception as e:
            logger.error(f"فشل الرفع: {str(e)}")
            return 1

    return 0


def handle_upload(args):
    """تنفيذ أمر رفع الملفات إلى Google Drive."""

    print("="*60)
    print("رافع الملفات إلى GOOGLE DRIVE")
    print("="*60)

    # التحقق من وجود المسار
    if not os.path.exists(args.path):
        logger.error(f"المسار غير موجود: {args.path}")
        return 1

    # رفع الملفات إلى Google Drive
    try:
        # تحميل وحدة الرفع
        upload_to_google_drive = get_uploader()

        results = upload_to_google_drive(
            args.path,
            args.folder_id,
            skip_existing=not args.no_skip
        )

        if results['failed']:
            logger.warning(
                f"فشل رفع بعض الملفات "
                f"({len(results['failed'])} عنصر)"
            )
            return 1

        logger.info("اكتمل الرفع بنجاح!")
        return 0

    except RuntimeError as e:
        # التعامل مع أخطاء البيئة أو التهيئة برسالة منسقة
        error_str = str(e)

        if error_str.startswith('\n'):
            # الرسالة منسقة بالفعل، لذلك يتم طباعتها مباشرة
            print(error_str)
        else:
            # إضافة تنسيق للرسالة
            print("\n" + "="*60)
            print("خطأ أثناء الرفع")
            print("="*60)
            print(error_str)
            print("="*60)

        return 1

    except Exception as e:
        logger.error(f"فشل الرفع: {str(e)}")
        return 1


def handle_status(args):
    """تنفيذ أمر التحقق من حالة التحميل."""

    if get_download_status():
        print("✓ تم العثور على جلسة تحميل متوقفة مؤقتًا")
        print(
            "  قم بتشغيل "
            "'python main.py download -t <torrent>' "
            "لاستكمال التحميل"
        )
        return 0

    else:
        print("✗ لم يتم العثور على جلسة تحميل متوقفة مؤقتًا")
        return 0


def handle_clear(args):
    """تنفيذ أمر مسح جلسة التحميل."""

    if clear_session():
        print("✓ تم مسح جلسة التحميل")
        return 0

    else:
        print("✗ فشل مسح جلسة التحميل")
        return 1


def main():
    """نقطة الدخول الرئيسية للبرنامج."""

    args = parse_arguments()

    # عرض المساعدة إذا لم يتم تحديد أي أمر
    if not args.command:
        print("خطأ: لم يتم تحديد أي أمر\n")
        parse_arguments().print_help()
        return 1

    try:
        # توجيه التنفيذ إلى الوظيفة المناسبة
        if args.command == 'download':
            return handle_download(args)

        elif args.command == 'upload':
            return handle_upload(args)

        elif args.command == 'status':
            return handle_status(args)

        elif args.command == 'clear':
            return handle_clear(args)

        else:
            logger.error(f"أمر غير معروف: {args.command}")
            return 1

    except KeyboardInterrupt:
        print("\n\nتم إلغاء العملية بواسطة المستخدم")

        if args.command == 'download':
            print(
                "تم حفظ تقدم التحميل. "
                "يمكنك استكماله باستخدام نفس الأمر."
            )

        return 130

    except Exception as e:
        logger.error(
            f"فشلت العملية: {str(e)}",
            exc_info=True
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())