import json
from typing import Dict, Any, Tuple
from config import INPUT_VIDEO, EDITMAP_JSON

def parse_job_input(job_input: Dict[str, Any]) -> Tuple[str, Any, str, str, str, bool]:
    """Parse and validate RunPod job input."""
    video_url = job_input.get('video_url')
    upload_url = job_input.get('upload_url')
    public_url = job_input.get('public_url')
    is_paid_user = job_input.get('is_paid_user', False)
    output_res = job_input.get('output_resolution', '720p')
    edit_json_url = job_input.get('edits_json_url') or job_input.get('edits_json')
    
    if not video_url or not edit_json_url:
        raise ValueError("Missing video_url or edits_json_url")
        
    return video_url, edit_json_url, upload_url, public_url, output_res, is_paid_user

def load_edit_data(edit_json_url: Any) -> Dict[str, Any]:
    """Load edit data from URL or direct object."""
    if isinstance(edit_json_url, str) and (edit_json_url.startswith("http") or len(edit_json_url) < 50):
        from storage.downloader import download_file
        download_file(edit_json_url, EDITMAP_JSON)
        with open(EDITMAP_JSON, "r") as f:
            return json.load(f)
    return edit_json_url if isinstance(edit_json_url, dict) else json.loads(edit_json_url)

