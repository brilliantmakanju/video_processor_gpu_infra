import os
import requests

def upload_to_r2(file_path: str, presigned_url: str):
    """Upload file to R2 using a presigned URL."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, 'rb') as f:
        response = requests.put(presigned_url, data=f)
        response.raise_for_status()
