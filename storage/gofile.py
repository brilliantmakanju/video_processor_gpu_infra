import os
import json
import subprocess
from typing import Optional, Dict, Any

def upload_to_gofile(file_path: str, api_token: Optional[str] = None) -> Dict[str, Any]:
    """Upload file to Gofile."""
    if not os.path.exists(file_path):
        return {"error": "File not found"}
    
    try:
        url = "https://upload.gofile.io/uploadfile"
        cmd = ["curl", "-F", f"file=@{file_path}"]
        if api_token:
            cmd.extend(["-H", f"Authorization: Bearer {api_token}"])
        cmd.append(url)
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        response = json.loads(result.stdout)
        if response.get("status") == "ok":
            return {"success": True, "download_url": response["data"]["downloadPage"]}
        return {"error": response.get("status")}
    except Exception as e:
        return {"error": str(e)}
