import libtorrent as lt
import time
import os
import sys

from config import (
    TORRENT_SESSION_FILE,
    TORRENT_DOWNLOAD_PATH,
    get_logger
)

logger = get_logger(__name__)


# ============================================================
# Session Management
# ============================================================

def save_session(session, session_file=TORRENT_SESSION_FILE):
    """
    Save the current libtorrent session state.
    """

    try:
        with open(session_file, "wb") as f:
            session_state = session.save_state()
            f.write(lt.bencode(session_state))

        logger.debug(
            f"Session saved to {session_file}"
        )

    except Exception as e:
        logger.error(
            f"Failed to save session: {e}"
        )


def load_session(session_file=TORRENT_SESSION_FILE):
    """
    Load a previously saved libtorrent session.

    If the session file is missing or invalid,
    create a new session.
    """

    if os.path.exists(session_file):

        try:
            with open(session_file, "rb") as f:
                session_data = f.read()

            if not session_data:
                raise ValueError(
                    "Session file is empty."
                )

            session_state = lt.bdecode(
                session_data
            )

            ses = lt.session()

            ses.load_state(
                session_state
            )

            logger.info(
                f"Loaded session from {session_file}"
            )

            return ses

        except (
            RuntimeError,
            ValueError,
            Exception
        ) as e:

            logger.warning(
                f"Failed to load session ({e}). "
                "Starting a new session."
            )

            try:
                os.remove(session_file)
            except OSError:
                pass

    return lt.session()


# ============================================================
# Formatting Helpers
# ============================================================

def format_speed(bytes_per_second):
    """
    Convert bytes/second to a human-readable speed.
    """

    value = max(0, int(bytes_per_second))

    if value >= 1024 ** 3:
        return f"{value / (1024 ** 3):.2f} GB/s"

    if value >= 1024 ** 2:
        return f"{value / (1024 ** 2):.2f} MB/s"

    if value >= 1024:
        return f"{value / 1024:.2f} KB/s"

    return f"{value} B/s"


def format_size(size):
    """
    Convert bytes to a human-readable size.
    """

    value = max(0, int(size))

    if value >= 1024 ** 4:
        return f"{value / (1024 ** 4):.2f} TB"

    if value >= 1024 ** 3:
        return f"{value / (1024 ** 3):.2f} GB"

    if value >= 1024 ** 2:
        return f"{value / (1024 ** 2):.2f} MB"

    if value >= 1024:
        return f"{value / 1024:.2f} KB"

    return f"{value} B"


def format_eta(seconds):
    """
    Convert ETA seconds to a readable string.
    """

    seconds = int(seconds)

    if seconds <= 0:
        return "Unknown"

    hours, remainder = divmod(
        seconds,
        3600
    )

    minutes, seconds = divmod(
        remainder,
        60
    )

    if hours > 0:
        return f"{hours}h {minutes}m"

    if minutes > 0:
        return f"{minutes}m {seconds}s"

    return f"{seconds}s"


def create_progress_bar(
    percent,
    length=30
):
    """
    Create a terminal progress bar.
    """

    percent = max(
        0.0,
        min(100.0, float(percent))
    )

    filled = int(
        length * percent / 100
    )

    filled = max(
        0,
        min(length, filled)
    )

    return (
        "█" * filled
        + "░" * (length - filled)
    )


# ============================================================
# Torrent Download
# ============================================================

def download_torrent(
    source,
    download_path=TORRENT_DOWNLOAD_PATH,
    session_file=TORRENT_SESSION_FILE,
    auto_resume=True
):
    """
    Download a torrent using libtorrent.

    Supports:
    - .torrent files
    - Magnet links
    - Session saving
    - Automatic resume
    - Telegram-friendly progress output
    """

    # --------------------------------------------------------
    # Prepare download directory
    # --------------------------------------------------------

    if not os.path.exists(download_path):

        os.makedirs(
            download_path,
            exist_ok=True
        )

        logger.info(
            f"Created download directory: {download_path}"
        )

    # --------------------------------------------------------
    # Load or create session
    # --------------------------------------------------------

    ses = (
        load_session(session_file)
        if auto_resume
        else lt.session()
    )

    # --------------------------------------------------------
    # Session settings
    # --------------------------------------------------------

    settings = {
        "listen_interfaces": "0.0.0.0:6881"
    }

    ses.apply_settings(
        settings
    )

    # --------------------------------------------------------
    # Torrent parameters
    # --------------------------------------------------------

    params = lt.add_torrent_params()

    params.save_path = download_path

    params.storage_mode = (
        lt.storage_mode_t.storage_mode_sparse
    )

    # --------------------------------------------------------
    # Add Magnet or Torrent file
    # --------------------------------------------------------

    if source.startswith("magnet:"):

        params.url = source

        logger.info(
            "Adding Magnet link..."
        )

    elif source.lower().endswith(".torrent"):

        if not os.path.exists(source):

            logger.error(
                f"Torrent file not found: {source}"
            )

            return None

        try:

            with open(
                source,
                "rb"
            ) as f:

                torrent_data = lt.bdecode(
                    f.read()
                )

            info = lt.torrent_info(
                torrent_data
            )

            params.ti = info

            logger.info(
                f"Adding torrent file: {source}"
            )

        except Exception as e:

            logger.error(
                f"Failed to read torrent file: {e}"
            )

            return None

    else:

        logger.error(
            "Invalid source. "
            "Please provide a .torrent file "
            "or a Magnet link."
        )

        return None

    # --------------------------------------------------------
    # Add torrent to session
    # --------------------------------------------------------

    try:

        handle = ses.add_torrent(
            params
        )

        logger.info(
            f"Download location: {download_path}"
        )

    except Exception as e:

        logger.error(
            f"Failed to add torrent: {e}"
        )

        return None

    # --------------------------------------------------------
    # Wait for metadata
    # --------------------------------------------------------

    logger.info(
        "Waiting for torrent metadata..."
    )

    metadata_start = time.time()

    while not handle.status().has_metadata:

        print(
            "\rTD_STATUS status=waiting_metadata",
            end="",
            flush=True
        )

        time.sleep(1)

        # Safety timeout:
        # keep the torrent alive but report status.
        if time.time() - metadata_start >= 10:

            logger.info(
                "Still waiting for torrent metadata..."
            )

            metadata_start = time.time()

    # --------------------------------------------------------
    # Torrent information
    # --------------------------------------------------------

    status = handle.status()

    torrent_name = status.name

    logger.info(
        f"Starting download: {torrent_name}"
    )

    # --------------------------------------------------------
    # Download loop
    # --------------------------------------------------------

    try:

        while True:

            s = handle.status()

            # ------------------------------------------------
            # Stop when torrent is completely downloaded
            # ------------------------------------------------

            if (
                s.state
                == lt.torrent_status.seeding
            ):

                break

            # ------------------------------------------------
            # Real libtorrent statistics
            # ------------------------------------------------

            progress = max(
                0.0,
                min(
                    100.0,
                    float(s.progress) * 100.0
                )
            )

            download_rate = max(
                0,
                int(s.download_rate)
            )

            upload_rate = max(
                0,
                int(s.upload_rate)
            )

            seeds = max(
                0,
                int(s.num_seeds)
            )

            peers = max(
                0,
                int(s.num_peers)
            )

            total_size = max(
                0,
                int(s.total_wanted)
            )

            downloaded = max(
                0,
                int(s.total_done)
            )

            remaining = max(
                0,
                total_size - downloaded
            )

            # ------------------------------------------------
            # ETA
            # ------------------------------------------------

            if (
                download_rate > 0
                and remaining > 0
            ):

                eta_seconds = int(
                    remaining / download_rate
                )

            else:

                eta_seconds = 0

            # ------------------------------------------------
            # Machine-readable progress
            #
            # The Telegram controller should parse
            # this line instead of parsing arbitrary logs.
            # ------------------------------------------------

            print(
                "\rTD_PROGRESS "
                f"percent={progress:.2f} "
                f"download_bps={download_rate} "
                f"upload_bps={upload_rate} "
                f"seeds={seeds} "
                f"peers={peers} "
                f"eta_seconds={eta_seconds} "
                f"downloaded={downloaded} "
                f"total={total_size}",
                end="",
                flush=True
            )

            # ------------------------------------------------
            # Human-readable terminal progress
            # ------------------------------------------------

            bar = create_progress_bar(
                progress,
                30
            )

            speed_str = format_speed(
                download_rate
            )

            upload_str = format_speed(
                upload_rate
            )

            eta_str = format_eta(
                eta_seconds
            )

            downloaded_str = format_size(
                downloaded
            )

            total_str = format_size(
                total_size
            )

            progress_line = (
                f"{bar} "
                f"{progress:.1f}% | "
                f"Download: {speed_str} | "
                f"Upload: {upload_str} | "
                f"Seeds: {seeds} | "
                f"Peers: {peers} | "
                f"ETA: {eta_str} | "
                f"{downloaded_str}/{total_str}"
            )

            print(
                "\r" + progress_line,
                end="",
                flush=True
            )

            # ------------------------------------------------
            # Save session periodically
            # ------------------------------------------------

            if int(time.time()) % 10 == 0:

                save_session(
                    ses,
                    session_file
                )

            time.sleep(1)

    except KeyboardInterrupt:

        print()

        logger.warning(
            "Download interrupted by user. "
            "Saving session for resume."
        )

        save_session(
            ses,
            session_file
        )

        return None

    except Exception as e:

        print()

        logger.error(
            f"Download error: {e}"
        )

        save_session(
            ses,
            session_file
        )

        return None

    # --------------------------------------------------------
    # Download completed
    # --------------------------------------------------------

    print()

    logger.info(
        "Download completed!"
    )

    # --------------------------------------------------------
    # Remove session file
    # --------------------------------------------------------

    if os.path.exists(
        session_file
    ):

        try:

            os.remove(
                session_file
            )

            logger.debug(
                "Removed session file "
                "after successful completion."
            )

        except Exception as e:

            logger.warning(
                f"Could not remove session file: {e}"
            )

    # --------------------------------------------------------
    # Return downloaded path
    # --------------------------------------------------------

    downloaded_path = os.path.join(
        download_path,
        torrent_name
    )

    return downloaded_path


# ============================================================
# Session Status
# ============================================================

def get_download_status(
    session_file=TORRENT_SESSION_FILE
):
    """
    Return True if a resumable session exists.
    """

    return os.path.exists(
        session_file
    )


# ============================================================
# Clear Session
# ============================================================

def clear_session(
    session_file=TORRENT_SESSION_FILE
):
    """
    Delete the saved torrent session.
    """

    if os.path.exists(
        session_file
    ):

        try:

            os.remove(
                session_file
            )

            logger.info(
                "Download session cleared."
            )

            return True

        except Exception as e:

            logger.error(
                f"Failed to clear session: {e}"
            )

            return False

    return True


# ============================================================
# Standalone Execution
# ============================================================

if __name__ == "__main__":

    if len(sys.argv) < 2:

        print(
            "Usage:\n"
            "  python torrent_downloader.py "
            "<torrent_file/magnet_link>"
        )

        sys.exit(1)

    source = sys.argv[1]

    result = download_torrent(
        source
    )

    if result:

        print(
            f"\nDownload completed successfully:\n"
            f"{result}"
        )

        sys.exit(0)

    else:

        sys.exit(1)
