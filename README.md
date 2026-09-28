# TeleDrive

A Python-based torrent management tool with Google Drive integration and Google Colab support.

> **Legal use only:** Use TeleDrive only with torrents, files, and content that you have the legal right to access, download, or upload.

## Overview

TeleDrive combines torrent downloading with Google Drive uploading in a simple command-line interface.

It can be used in Google Colab or as a standalone Python application.

## Features

- Torrent downloading using libtorrent
- Magnet link and `.torrent` file support
- Automatic Google Drive uploads
- Resume support for interrupted downloads
- Real-time download progress
- Duplicate file detection
- Configurable download location
- Configurable Google Drive destination
- Google Colab support
- Google Drive authentication
- Command-line interface
- Download session management

## Google Colab

TeleDrive can be run directly from Google Colab.

### Open in Google Colab

[Open TeleDrive in Google Colab](https://colab.research.google.com/github/AbdoNode/TeleDrive/blob/main/TeleDrive_V2.ipynb)

The notebook handles the basic installation and Google authentication required by the project.

## Installation

### Clone the repository

```bash
git clone https://github.com/AbdoNode/TeleDrive.git
cd TeleDrive
```

### Install dependencies

```bash
pip install -r requirements.txt
```

Depending on your operating system, libtorrent may require additional system dependencies.

## Usage

### Download a torrent

Using a magnet link:

```bash
python main.py download -t "magnet:?xt=urn:btih:..."
```

Using a `.torrent` file:

```bash
python main.py download -t path/to/file.torrent
```

### Download and upload to Google Drive

```bash
python main.py download -t "magnet:?xt=urn:btih:..." --upload
```

When `--upload` is enabled, downloaded files are uploaded to Google Drive after the download process.

### Upload an existing file or folder

```bash
python main.py upload -p /path/to/file
```

Or:

```bash
python main.py upload -p /path/to/folder
```

### Upload to a specific Google Drive folder

Use the `-f` option with the Google Drive folder ID:

```bash
python main.py download -t "magnet:?xt=urn:btih:..." --upload -f FOLDER_ID
```

For existing files:

```bash
python main.py upload -p /path/to/folder -f FOLDER_ID
```

## Commands

### Check download status

```bash
python main.py status
```

### Clear the current torrent session

```bash
python main.py clear
```

## Command Options

### Download

```text
-t, --torrent
```

Torrent source. This can be a magnet link or a `.torrent` file.

```text
--upload
```

Upload completed files to Google Drive.

```text
--no-resume
```

Ignore the previous torrent session and start a new download.

```text
-d PATH
```

Specify a custom download directory.

```text
-f FOLDER_ID
```

Specify a Google Drive folder ID for uploads.

### Upload

```text
-p PATH
```

Path to the file or folder that should be uploaded.

```text
-f FOLDER_ID
```

Specify the destination Google Drive folder.

```text
--no-skip
```

Upload files even if matching files already exist in Google Drive.

## Google Drive

TeleDrive can automatically create and use a Google Drive folder named:

```text
Torrent Downloads
```

The folder is created in the Google Drive root when necessary.

If you want to use another folder, provide its Google Drive folder ID with:

```bash
-f FOLDER_ID
```

### Finding a Google Drive Folder ID

1. Open Google Drive.
2. Open the destination folder.
3. Copy the folder ID from the folder URL.

Example:

```text
https://drive.google.com/drive/folders/FOLDER_ID
```

Use the value after `/folders/` as the folder ID.

## Configuration

Project configuration is handled by `config.py`.

Important settings include:

```python
TORRENT_DOWNLOAD_PATH = "../Torrent Downloads"
CHUNK_SIZE = 100 * 1024 * 1024
MAX_RETRIES = 3
LARGE_FILE_THRESHOLD = 1024 * 1024 * 1024
```

The exact available configuration options depend on the current version of `config.py`.

## Project Structure

```text
TeleDrive/
├── main.py
├── torrent_downloader.py
├── gdrive_uploader.py
├── config.py
├── requirements.txt
├── TeleDrive.ipynb
├── LICENSE
└── README.md
```

### Main Files

| File | Description |
|---|---|
| `main.py` | Main command-line interface |
| `torrent_downloader.py` | Torrent downloading and session management |
| `gdrive_uploader.py` | Google Drive upload functionality |
| `config.py` | Configuration and logging |
| `requirements.txt` | Python dependencies |
| `TeleDrive.ipynb` | Google Colab notebook |

## Google Colab Workflow

A typical Colab workflow is:

```text
Open TeleDrive.ipynb
        ↓
Clone TeleDrive
        ↓
Install dependencies
        ↓
Authenticate Google Drive
        ↓
Run TeleDrive
        ↓
Download files
        ↓
Upload files to Google Drive
```

Google Colab runtimes are temporary environments. Files stored only inside the temporary runtime may be lost when the runtime ends.

## Telegram Bot

TeleDrive can also be controlled from Telegram when using the Telegram-enabled Colab notebook.

The bot can provide commands such as:

```text
/start
/help
/ping
/download
/status
/upload
/clear
/stop
```

A Telegram bot token should be stored securely using Google Colab Secrets rather than being written directly into the notebook.

For additional security, an allowed Telegram user ID can be configured so that only an authorized user can control the bot.

> Only use the Telegram interface with content and files that you are legally authorized to access or manage.

## Requirements

TeleDrive requires Python and the dependencies listed in:

```text
requirements.txt
```

The project uses libtorrent for torrent functionality and Google APIs for Google Drive integration.

## Supported Environments

TeleDrive is primarily designed for:

- Google Colab
- Linux
- macOS
- WSL environments

Compatibility with other environments depends on the available libtorrent and Google API dependencies.

## Legal Notice

TeleDrive is a software tool and does not provide or distribute torrent content.

You are responsible for ensuring that your use of TeleDrive complies with:

- Copyright laws
- Intellectual property laws
- Local regulations
- The terms of the services you use

Only download, store, or upload content that you have the legal right or permission to use.

## Contributing

Contributions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Make your changes.
4. Test the changes.
5. Submit a pull request.

## License

This project is licensed under the Apache License 2.0.

See [`LICENSE`](LICENSE) for the complete license text.

## Links

- [GitHub Repository](https://github.com/AbdoNode/TeleDrive)
- [Issues](https://github.com/AbdoNode/TeleDrive/issues)
- [Google Colab Notebook](https://colab.research.google.com/github/AbdoNode/TeleDrive/blob/main/TeleDrive.ipynb)

---

**TeleDrive**
