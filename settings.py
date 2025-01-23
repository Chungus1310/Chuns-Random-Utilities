import json
import os
from pathlib import Path

class Settings:
    def __init__(self):
        self.config_file = 'config.json'
        self.defaults = {
            'extension_mappings': {
                'Images': ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg'],
                'Documents': ['.pdf', '.docx', '.doc', '.xlsx', '.pptx', '.txt'],
                'Archives': ['.zip', '.rar', '.7z', '.tar', '.gz']
            },
            'last_folders': {
                'downloads': '',
                'duplicates': ''
            }
        }
        self.settings = self.defaults.copy()
        self.load()
    
    def validate_settings(self):
        """Validate and repair settings structure"""
        valid = True
        for key in self.defaults:
            if key not in self.settings:
                self.settings[key] = self.defaults[key]
                valid = False
        
        # Validate extension mappings structure
        if not isinstance(self.settings['extension_mappings'], dict):
            self.settings['extension_mappings'] = self.defaults['extension_mappings']
            valid = False
        
        return valid
    
    def load(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    loaded_settings = json.load(f)
                self.settings.update(loaded_settings)
                
                if not self.validate_settings():
                    print("Settings were corrupted and have been repaired")
                    self.save()
        except Exception as e:
            print(f"Error loading settings: {e}")
            self.settings = self.defaults.copy()
            self.save()
    
    def save(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def get_extension_mappings(self):
        return self.settings.get('extension_mappings', self.defaults['extension_mappings'])
    
    def set_extension_mappings(self, mappings):
        self.settings['extension_mappings'] = mappings
        self.save()
    
    def get_last_folder(self, key):
        return self.settings.get('last_folders', {}).get(key, '')
    
    def set_last_folder(self, key, path):
        if 'last_folders' not in self.settings:
            self.settings['last_folders'] = {}
        self.settings['last_folders'][key] = path
        self.save()

    def export_template(self, filepath):
        try:
            with open(filepath, 'w') as f:
                json.dump({
                    'extension_mappings': self.settings.get('extension_mappings', {})
                }, f, indent=4)
            return True
        except Exception as e:
            print(f"Error exporting template: {e}")
            return False

    def import_template(self, filepath):
        try:
            with open(filepath, 'r') as f:
                template = json.load(f)
                if 'extension_mappings' in template:
                    self.settings['extension_mappings'] = template['extension_mappings']
                    self.save()
                    return True
            return False
        except Exception as e:
            print(f"Error importing template: {e}")
            return False
