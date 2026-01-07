import os
import requests
from utils.retry import retry

@retry(requests.exceptions.RequestException, tries=3, delay=2, backoff=2)
def upload_to_r2(file_path: str, presigned_url: str):
    """Upload file to R2 using a presigned URL with retry logic."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, 'rb') as f:
        # Use a reasonable timeout for upload
        # IMPORTANT: Content-Type must match what was used to generate the presigned URL
        headers = {"Content-Type": "video/mp4"}
        response = requests.put(presigned_url, data=f, headers=headers, timeout=(10, 600))
        response.raise_for_status()
