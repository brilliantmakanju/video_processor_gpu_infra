import json
from typing import Dict, Any, Tuple
from config import INPUT_VIDEO, EDITMAP_JSON

def parse_job_input(job_input: Dict[str, Any]) -> Tuple[str, Any, str, str, str, bool]:
    """Parse and validate RunPod job input with strict checks."""
    if not isinstance(job_input, dict):
        raise ValueError("Job input must be a dictionary")

    video_url = job_input.get('video_url')
    upload_url = job_input.get('upload_url')
    public_url = job_input.get('public_url')
    is_paid_user = job_input.get('is_paid_user', False)
    output_res = job_input.get('output_resolution', '720p')
    edit_json_url = job_input.get('edits_json_url') or job_input.get('edits_json')
    
    if not video_url or not isinstance(video_url, str) or not video_url.startswith("http"):
        raise ValueError("Missing or invalid video_url (must be a valid HTTP URL)")
        
    if not edit_json_url:
        raise ValueError("Missing edits_json_url or edits_json")
        
    if output_res not in ['720p', '1080p', '1440p', '4k', 'original']:
        output_res = '720p' # Fallback to safe default
        
    return video_url, edit_json_url, upload_url, public_url, output_res, bool(is_paid_user)

def load_edit_data(edit_json_url: Any) -> Dict[str, Any]:
    """Load edit data from URL or direct object."""
    if isinstance(edit_json_url, str) and (edit_json_url.startswith("http") or len(edit_json_url) < 50):
        from storage.downloader import download_file
        download_file(edit_json_url, EDITMAP_JSON, 8192, 120)
        with open(EDITMAP_JSON, "r") as f:
            return json.load(f)
    return edit_json_url if isinstance(edit_json_url, dict) else json.loads(edit_json_url)

