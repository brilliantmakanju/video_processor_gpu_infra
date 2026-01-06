import subprocess

def download_from_gdrive(file_id: str, output_path: str):
    """Download file from Google Drive."""
    try:
        import gdown
        url = f"https://drive.google.com/uc?id={file_id}"
        gdown.download(url, output_path, quiet=False)
    except Exception:
        direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        subprocess.check_call(["curl", "-L", "-o", output_path, direct_url])
