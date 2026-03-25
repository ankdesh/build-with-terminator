import os
import yaml
import uuid
from datetime import datetime
from pathlib import Path

BUGS_DIR = Path('bugs')
ATTACHMENTS_DIR = Path('attachments')

def init_dirs():
    """Ensure data directories exist."""
    BUGS_DIR.mkdir(parents=True, exist_ok=True)
    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)

def save_bug(data: dict) -> str:
    """Save bug data to a new YAML file. Returns the generated bug ID."""
    init_dirs()
    
    bug_id = str(uuid.uuid4())
    data['id'] = bug_id
    data['created_at'] = datetime.now().isoformat()
    if 'comments' not in data:
        data['comments'] = []
    
    file_path = BUGS_DIR / f"{bug_id}.yaml"
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        
    return bug_id

def load_bugs() -> list[dict]:
    """Load all bugs from the bugs directory, sorted by creation date."""
    init_dirs()
    
    bugs = []
    for filepath in BUGS_DIR.glob('*.yaml'):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                bug_data = yaml.safe_load(f)
                if bug_data:
                    bugs.append(bug_data)
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            
    # Sort bugs by created_at descending (newest first)
    bugs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return bugs

def add_comment(bug_id: str, author: str, text: str) -> bool:
    """Add a comment to an existing bug."""
    file_path = BUGS_DIR / f"{bug_id}.yaml"
    if not file_path.exists():
        return False
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            bug_data = yaml.safe_load(f)
            
        if not bug_data:
            return False
            
        if 'comments' not in bug_data:
            bug_data['comments'] = []
            
        comment = {
            'author': author if author else 'Anonymous',
            'timestamp': datetime.now().isoformat(),
            'text': text
        }
        bug_data['comments'].append(comment)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(bug_data, f, default_flow_style=False, sort_keys=False)
            
        return True
    except Exception as e:
        print(f"Error adding comment to {bug_id}: {e}")
        return False

def get_bug(bug_id: str) -> dict | None:
    """Get a single bug by ID."""
    file_path = BUGS_DIR / f"{bug_id}.yaml"
    if not file_path.exists():
        return None
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error reading {bug_id}: {e}")
        return None
