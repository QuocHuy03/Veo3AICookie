import json
import os
import base64
import time
import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import hashlib

class ConfigManager:
    """Quản lý cấu hình app, bao gồm lưu trữ key đã mã hóa"""
    
    def __init__(self, config_file="app_config.json"):
        self.config_file = config_file
        self.config = self._load_config()
        
    def _load_config(self):
        """Tải cấu hình từ file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
    
    def _save_config(self):
        """Lưu cấu hình vào file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
    
    def _get_encryption_key(self, device_id):
        """Tạo key mã hóa từ device_id"""
        # Sử dụng device_id làm password để tạo key mã hóa
        password = f"whisk_key_{device_id}".encode()
        salt = b"whisk_salt_2024"  # Salt cố định cho app
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return Fernet(key)
    
    def save_api_key(self, api_key, device_id, key_info=None, remember=True):
        """Lưu API key đã mã hóa cùng với thông tin expiry"""
        if not remember:
            # Nếu không muốn lưu, xóa key cũ nếu có
            self.clear_api_key()
            return True
            
        try:
            # Mã hóa key
            fernet = self._get_encryption_key(device_id)
            encrypted_key = fernet.encrypt(api_key.encode())
            
            # Lưu vào config
            saved_data = {
                'encrypted_key': base64.b64encode(encrypted_key).decode(),
                'device_hash': hashlib.sha256(device_id.encode()).hexdigest()[:16],  # Hash ngắn để verify
                'saved_at': int(time.time())  # Thời gian lưu
            }
            
            # Lưu thêm thông tin key nếu có
            if key_info:
                saved_data.update({
                    'expires': key_info.get('expires', ''),
                    'remaining': key_info.get('remaining', 0),
                    'device_id_display': key_info.get('device_id', '')
                })
            
            self.config['saved_key'] = saved_data
            return self._save_config()
        except Exception:
            return False
    
    def get_saved_api_key(self, device_id):
        """Lấy API key đã lưu và giải mã, trả về tuple (key, key_info)"""
        if 'saved_key' not in self.config:
            return None, None
            
        try:
            saved_data = self.config['saved_key']
            
            # Kiểm tra device hash để đảm bảo key được lưu trên cùng máy
            current_hash = hashlib.sha256(device_id.encode()).hexdigest()[:16]
            if saved_data.get('device_hash') != current_hash:
                # Key được lưu trên máy khác, xóa key cũ
                self.clear_api_key()
                return None, None
            
            # Giải mã key
            fernet = self._get_encryption_key(device_id)
            encrypted_key = base64.b64decode(saved_data['encrypted_key'])
            decrypted_key = fernet.decrypt(encrypted_key).decode()
            
            # Tạo key_info từ dữ liệu đã lưu
            key_info = {
                'key': decrypted_key,
                'expires': saved_data.get('expires', ''),
                'remaining': saved_data.get('remaining', 0),
                'device_id': saved_data.get('device_id_display', ''),
                'saved_at': saved_data.get('saved_at', 0)
            }
            
            return decrypted_key, key_info
        except Exception:
            # Nếu có lỗi giải mã, xóa key cũ
            self.clear_api_key()
            return None, None
    
    def clear_api_key(self):
        """Xóa API key đã lưu"""
        if 'saved_key' in self.config:
            del self.config['saved_key']
            return self._save_config()
        return True
    
    def has_saved_key(self):
        """Kiểm tra có key đã lưu không"""
        return 'saved_key' in self.config
    
    def is_key_expired_locally(self, device_id):
        """Kiểm tra key đã hết hạn dựa trên thông tin local (không cần request server)"""
        if 'saved_key' not in self.config:
            return True
            
        try:
            saved_data = self.config['saved_key']
            expires_str = saved_data.get('expires', '')
            
            if not expires_str or expires_str.lower() in ['unknown', 'unlimited', 'never']:
                # Nếu không có thông tin expiry hoặc không giới hạn, coi như chưa hết hạn
                return False
            
            # Parse expiry date - thử nhiều format
            expiry_formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d',
                '%d/%m/%Y %H:%M:%S',
                '%d/%m/%Y',
                '%m/%d/%Y %H:%M:%S',
                '%m/%d/%Y'
            ]
            
            expiry_date = None
            for fmt in expiry_formats:
                try:
                    expiry_date = datetime.datetime.strptime(expires_str, fmt)
                    break
                except ValueError:
                    continue
            
            if expiry_date is None:
                # Không parse được date, coi như chưa hết hạn để tránh false positive
                return False
            
            # So sánh với thời gian hiện tại
            now = datetime.datetime.now()
            return now > expiry_date
            
        except Exception:
            # Nếu có lỗi, coi như chưa hết hạn để tránh false positive
            return False
    
    def should_refresh_key(self, device_id, force_refresh_hours=24):
        """Kiểm tra có nên refresh key không (dựa trên thời gian lưu)"""
        if 'saved_key' not in self.config:
            return True
            
        try:
            saved_data = self.config['saved_key']
            saved_at = saved_data.get('saved_at', 0)
            
            if saved_at == 0:
                return True
            
            # Kiểm tra đã lưu quá lâu chưa (mặc định 24h)
            hours_since_saved = (time.time() - saved_at) / 3600
            return hours_since_saved > force_refresh_hours
            
        except Exception:
            return True
    
    def get_config_value(self, key, default=None):
        """Lấy giá trị config khác"""
        return self.config.get(key, default)
    
    def set_config_value(self, key, value):
        """Đặt giá trị config khác"""
        self.config[key] = value
        return self._save_config()