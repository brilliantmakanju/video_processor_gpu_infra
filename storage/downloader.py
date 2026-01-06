import requests
from storage.gdrive import download_from_gdrive

def download_file(url: str, output_path: str):
    """Generic downloader."""
    if "drive.google.com" in url:
        file_id = url
        if "id=" in url:
            file_id = url.split("id=")[1].split("&")[0]
        download_from_gdrive(file_id, output_path)
    else:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
