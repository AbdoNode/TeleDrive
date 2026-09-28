import libtorrent as lt
import time
import os
import sys
from config import TORRENT_SESSION_FILE, TORRENT_DOWNLOAD_PATH, get_logger

logger = get_logger(__name__)


# التحقق مما إذا كان البرنامج يعمل داخل Google Colab
try:
    from google.colab import files
    IN_COLAB = True
except ImportError:
    IN_COLAB = False


def save_session(session, session_file=TORRENT_SESSION_FILE):
    """حفظ حالة جلسة التحميل لاستكمالها لاحقًا (يتم حفظ البيانات الثنائية بشكل صحيح)."""
    try:
        with open(session_file, "wb") as f:
            session_state = session.save_state()
            f.write(lt.bencode(session_state))

        logger.debug(f"تم حفظ الجلسة في {session_file}")

    except Exception as e:
        logger.error(f"فشل حفظ الجلسة: {e}")


def load_session(session_file=TORRENT_SESSION_FILE):
    """تحميل حالة الجلسة إذا كانت موجودة، وإلا إنشاء جلسة جديدة."""

    if os.path.exists(session_file):
        try:
            with open(session_file, "rb") as f:
                session_data = f.read()

                if not session_data:
                    raise ValueError("ملف الجلسة فارغ.")

                session_state = lt.bdecode(session_data)

                ses = lt.session()
                ses.load_state(session_state)

                logger.info(
                    f"تم تحميل الجلسة من {session_file}"
                )

                return ses

        except (RuntimeError, ValueError) as e:
            logger.warning(
                f"فشل تحميل الجلسة ({e}). سيتم بدء جلسة جديدة."
            )

            os.remove(session_file)

    return lt.session()


def download_torrent(
    source,
    download_path=TORRENT_DOWNLOAD_PATH,
    session_file=TORRENT_SESSION_FILE,
    auto_resume=True
):
    """
    تحميل ملف Torrent باستخدام libtorrent
    مع دعم الإيقاف والاستكمال.

    :param source:
        مسار ملف .torrent أو رابط Magnet.

    :param download_path:
        المجلد الذي سيتم حفظ المحتوى الذي تم تحميله بداخله.

    :param session_file:
        الملف المستخدم لحفظ وتحميل حالة جلسة التحميل.

    :param auto_resume:
        تحميل الجلسة السابقة تلقائيًا إذا كانت متاحة.

    :return:
        مسار المحتوى الذي تم تحميله، أو None في حالة فشل العملية.
    """

    if not os.path.exists(download_path):
        os.makedirs(download_path)

        logger.info(
            f"تم إنشاء مجلد التحميل: {download_path}"
        )

    # التحقق مما إذا كان سيتم استكمال جلسة تحميل سابقة
    is_resuming = (
        auto_resume
        and os.path.exists(session_file)
    )

    # تحميل الجلسة الحالية أو إنشاء جلسة جديدة
    ses = (
        load_session(session_file)
        if auto_resume
        else lt.session()
    )

    # تطبيق الإعدادات المطلوبة
    settings = {
        'listen_interfaces': '0.0.0.0:6881',
    }

    ses.apply_settings(settings)

    # تهيئة إعدادات إضافة Torrent
    params = lt.add_torrent_params()

    params.save_path = download_path
    params.storage_mode = (
        lt.storage_mode_t.storage_mode_sparse
    )

    # التعامل مع رابط Magnet أو ملف .torrent
    if source.startswith("magnet:"):

        params.url = source

        logger.info(
            f"إضافة رابط Magnet: {source[:60]}..."
        )

    elif source.endswith(".torrent"):

        if not os.path.exists(source):
            logger.error(
                f"ملف Torrent غير موجود: {source}"
            )
            return None

        try:
            with open(source, "rb") as f:
                torrent_data = lt.bdecode(f.read())
                info = lt.torrent_info(torrent_data)
                params.ti = info

            logger.info(
                f"إضافة ملف Torrent: {source}"
            )

        except Exception as e:
            logger.error(
                f"فشل قراءة ملف Torrent: {e}"
            )
            return None

    else:
        logger.error(
            "مصدر غير صالح. "
            "يرجى توفير ملف .torrent أو رابط Magnet."
        )
        return None

    # إضافة Torrent إلى جلسة التحميل
    try:
        handle = ses.add_torrent(params)

        logger.info(
            f"التحميل إلى: {download_path}"
        )

    except Exception as e:
        logger.error(
            f"فشل إضافة Torrent: {e}"
        )
        return None

    # انتظار الحصول على بيانات Torrent
    logger.info("في انتظار بيانات Torrent...")

    while not handle.status().has_metadata:
        time.sleep(1)

    torrent_name = handle.status().name

    logger.info(
        f"جاري التحميل: {torrent_name}"
    )

    try:

        while (
            handle.status().state
            != lt.torrent_status.seeding
        ):

            s = handle.status()

            progress = s.progress * 100

            # حساب الوقت المتبقي للتحميل
            eta_str = "غير معروف"

            if s.download_rate > 0:

                total_size = s.total_wanted
                downloaded = s.total_done
                remaining = total_size - downloaded

                eta_seconds = (
                    remaining / s.download_rate
                )

                if eta_seconds < 60:
                    eta_str = f"{int(eta_seconds)}ث"

                elif eta_seconds < 3600:
                    eta_str = (
                        f"{int(eta_seconds / 60)}د "
                        f"{int(eta_seconds % 60)}ث"
                    )

                else:
                    hours = int(
                        eta_seconds / 3600
                    )

                    minutes = int(
                        (eta_seconds % 3600) / 60
                    )

                    eta_str = (
                        f"{hours}س {minutes}د"
                    )

            # تنسيق سرعة التحميل
            if s.download_rate > 1024 * 1024:
                speed_str = (
                    f"{s.download_rate / (1024 * 1024):.2f} MB/s"
                )
            else:
                speed_str = (
                    f"{s.download_rate / 1024:.2f} KB/s"
                )

            # إنشاء شريط التقدم يدويًا
            bar_length = 30

            filled_length = int(
                bar_length * progress / 100
            )

            bar = (
                '█' * filled_length
                + '░' * (
                    bar_length - filled_length
                )
            )

            # تحديد اسم الحالة بناءً على الحالة الفعلية
            if is_resuming and progress < 95:

                label = "استكمال التحميل"

            elif (
                s.download_rate == 0
                and s.num_peers == 0
            ):

                label = "جاري الاتصال بالمصادر"

            else:

                label = "تقدم التحميل"

                # لم يعد التحميل في وضع الاستكمال
                # بعد بدء التحميل الفعلي
                is_resuming = False

            stats_str = (
                f"المصادر: {s.num_seeds} | "
                f"المتصلون: {s.num_peers - s.num_seeds} | "
                f"السرعة: {speed_str} | "
                f"الوقت المتبقي: {eta_str}"
            )

            progress_line = (
                f"{label}: "
                f"{bar} "
                f"{progress:.1f}/100%    | "
                f"{stats_str}"
            )

            # استخدام print بدلًا من tqdm لتجنب التداخل
            print(
                f"\r{progress_line}",
                end="",
                flush=True
            )

            # حفظ الجلسة بشكل دوري كل 10 ثوانٍ
            if int(time.time()) % 10 == 0:
                save_session(
                    ses,
                    session_file
                )

            time.sleep(1)

    except KeyboardInterrupt:

        # الانتقال إلى سطر جديد بعد شريط التقدم
        print()

        logger.warning(
            "تم إيقاف التحميل بواسطة المستخدم. "
            "تم حفظ الجلسة لاستكمالها لاحقًا."
        )

        save_session(
            ses,
            session_file
        )

        return None

    # الانتقال إلى سطر جديد بعد اكتمال شريط التقدم
    print()

    logger.info("اكتمل التحميل!")

    # حذف ملف الجلسة بعد اكتمال التحميل بنجاح
    if os.path.exists(session_file):

        try:
            os.remove(session_file)

            logger.debug(
                "تم حذف ملف الجلسة بعد اكتمال التحميل بنجاح"
            )

        except Exception as e:

            logger.warning(
                f"تعذر حذف ملف الجلسة: {e}"
            )

    # إرجاع مسار المحتوى الذي تم تحميله
    downloaded_path = os.path.join(
        download_path,
        torrent_name
    )

    return downloaded_path


def get_download_status(
    session_file=TORRENT_SESSION_FILE
):
    """
    التحقق مما إذا كان هناك تحميل متوقف
    يمكن استكماله.

    :return:
        True إذا كان ملف الجلسة موجودًا،
        وFalse إذا لم يكن موجودًا.
    """

    return os.path.exists(session_file)


def clear_session(
    session_file=TORRENT_SESSION_FILE
):
    """
    حذف ملف الجلسة لبدء تحميل جديد.

    :return:
        True إذا تم الحذف بنجاح،
        وFalse إذا فشلت العملية.
    """

    if os.path.exists(session_file):

        try:
            os.remove(session_file)

            logger.info(
                "تم مسح ملف الجلسة"
            )

            return True

        except Exception as e:

            logger.error(
                f"فشل مسح الجلسة: {e}"
            )

            return False

    return True


if __name__ == "__main__":

    if len(sys.argv) < 2:

        print(
            "الاستخدام: "
            "python torrent_downloader.py "
            "<torrent_file/magnet_link>"
        )

        sys.exit(1)

    source = sys.argv[1]

    result = download_torrent(source)

    if result:

        print(
            f"\nتم التحميل إلى: {result}"
        )

        sys.exit(0)

    else:

        sys.exit(1)