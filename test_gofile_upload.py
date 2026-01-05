import os
import json
import subprocess
from typing import Optional, Dict, Any

def upload_to_gofile(file_path: str, api_token: Optional[str] = None) -> Dict[str, Any]:
    """Upload file to Gofile using curl and return the download URL."""
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}
    
    print(f"📤 Uploading {os.path.basename(file_path)} to Gofile...")
    
    try:
        url = "https://upload.gofile.io/uploadfile"
        
        cmd = ["curl", "-F", f"file=@{file_path}"]
        if api_token:
            cmd.extend(["-H", f"Authorization: Bearer {api_token}"])
        
        cmd.append(url)
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode != 0:
            return {"error": f"Curl failed: {result.stderr}"}
        
        response = json.loads(result.stdout)
        if response.get("status") == "ok":
            data = response.get("data", {})
            print(f"✅ Upload successful: {data.get('downloadPage')}")
            return {
                "success": True,
                "download_url": data.get("downloadPage"),
                "file_id": data.get("fileId"),
                "folder_id": data.get("folderId"),
                "md5": data.get("md5")
            }
        else:
            return {"error": f"Gofile error: {response.get('status')}"}
            
    except Exception as e:
        print(f"❌ Upload failed: {str(e)}")
        return {"error": str(e)}

def test_upload():
    # Create a small dummy file
    dummy_file = "test_upload.txt"
    with open(dummy_file, "w") as f:
        f.write("This is a test upload for Spliceo V2 Ultra.")
    
    # Test upload without token (guest account)
    print("Testing guest upload...")
    result = upload_to_gofile(dummy_file)
    print(f"Result: {json.dumps(result, indent=2)}")
    
    # Clean up
    if os.path.exists(dummy_file):
        os.remove(dummy_file)

if __name__ == "__main__":
    test_upload()
