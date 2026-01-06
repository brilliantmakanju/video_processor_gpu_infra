import requests
from storage.gdrive import download_from_gdrive


def download_file(
    url: str,
    output_path: str,
    chunk_size: int = 8192,
    timeout: int = 60,
):
    """
    Generic downloader with Google Drive support and progress logging.
    """

    print(f"[DOWNLOAD] Starting")
    print(f"[DOWNLOAD] Source: {url}")
    print(f"[DOWNLOAD] Output: {output_path}")

    # --- Google Drive handling ---
    if "drive.google.com" in url:
        print("[DOWNLOAD] Detected Google Drive URL")

        file_id = None

        if "id=" in url:
            file_id = url.split("id=")[1].split("&")[0]
        elif "/d/" in url:
            file_id = url.split("/d/")[1].split("/")[0]

        if not file_id:
            raise ValueError("Unable to extract Google Drive file ID")

        print(f"[DOWNLOAD] Google Drive file ID: {file_id}")
        download_from_gdrive(file_id, output_path)
        print("[DOWNLOAD] Google Drive download completed")
        return

    # --- Standard HTTP(S) download ---
    response = requests.get(url, stream=True, timeout=timeout)
    response.raise_for_status()

    total_size = int(response.headers.get("Content-Length", 0))
    downloaded = 0

    if total_size:
        print(f"[DOWNLOAD] File size: {total_size / (1024 * 1024):.2f} MB")
    else:
        print("[DOWNLOAD] File size unknown")

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if not chunk:
                continue

            f.write(chunk)
            downloaded += len(chunk)

            if total_size:
                percent = (downloaded / total_size) * 100
                print(
                    f"\r[DOWNLOAD] {percent:6.2f}% "
                    f"({downloaded / (1024 * 1024):.2f} MB)",
                    end="",
                    flush=True,
                )

    print("\n[DOWNLOAD] Download completed successfully")