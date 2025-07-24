import requests
import json
import os
import re
from typing import Dict, Optional
from .config import Config

class FileDownloader:
    def __init__(self):
        self.download_dir = Config.DOWNLOAD_DIR
    
    def extract_drive_file_id(self, url: str) -> Optional[str]:
        """Extract file ID from Google Drive URL"""
        patterns = [
            r'/file/d/([a-zA-Z0-9-_]+)',
            r'id=([a-zA-Z0-9-_]+)',
            r'/([a-zA-Z0-9-_]+)/view',
            r'/([a-zA-Z0-9-_]+)/edit'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def convert_drive_url(self, url: str) -> str:
        """Convert Google Drive sharing URL to direct download URL"""
        if 'drive.google.com' in url:
            file_id = self.extract_drive_file_id(url)
            if file_id:
                return f"https://drive.google.com/uc?id={file_id}&export=download"
        return url
    
    def download_json_file(self, url: str, filename: str) -> Dict:
        """Download JSON file from URL"""
        try:
            # Convert Drive URL if needed
            download_url = self.convert_drive_url(url)
            
            print(f"📥 Downloading: {filename}")
            response = requests.get(download_url, timeout=30)
            response.raise_for_status()
            
            # Parse JSON
            json_data = response.json()
            
            # Save to local file
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2)
            
            print(f"✅ Downloaded and saved: {filename}")
            return json_data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Request error downloading {filename}: {e}")
            return {}
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error for {filename}: {e}")
            return {}
        except Exception as e:
            print(f"❌ Unexpected error downloading {filename}: {e}")
            return {}
    
    def download_llm_files(self, row_data: Dict) -> Dict:
        """Download all LLM files for a given row"""
        task_id = row_data['task_id']
        row_number = row_data['row_number']
        
        downloaded_files = {}
        
        for llm_name, file_url in row_data['llm_files'].items():
            if not file_url:
                continue
            
            # Create filename
            filename = f"{task_id}_{llm_name}_row{row_number}.json"
            filepath = os.path.join(self.download_dir, llm_name, filename)
            
            # Download file
            json_data = self.download_json_file(file_url, filepath)
            
            if json_data:
                downloaded_files[llm_name] = {
                    'filepath': filepath,
                    'data': json_data,
                    'url': file_url
                }
        
        return downloaded_files
    
    def get_local_file(self, llm_name: str, task_id: str, row_number: int) -> Optional[Dict]:
        """Get locally stored file if it exists"""
        filename = f"{task_id}_{llm_name}_row{row_number}.json"
        filepath = os.path.join(self.download_dir, llm_name, filename)
        
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"❌ Error reading local file {filepath}: {e}")
        
        return None
    
    def cleanup_old_files(self, days_old: int = 7):
        """Clean up downloaded files older than specified days"""
        import time
        
        current_time = time.time()
        cutoff_time = current_time - (days_old * 24 * 60 * 60)
        
        for llm_name in Config.LLM_COLUMNS.keys():
            llm_dir = os.path.join(self.download_dir, llm_name)
            if os.path.exists(llm_dir):
                for filename in os.listdir(llm_dir):
                    filepath = os.path.join(llm_dir, filename)
                    if os.path.getmtime(filepath) < cutoff_time:
                        os.remove(filepath)
                        print(f"🗑️ Cleaned up old file: {filename}")