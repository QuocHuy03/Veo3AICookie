import uuid
import hashlib
import platform
import subprocess
import requests
import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QHBoxLayout, QSpacerItem, QSizePolicy, QProgressBar, QTextEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from requests.exceptions import RequestException, ConnectionError, Timeout

SECRET_SALT = "huydev"


def get_device_id():
    """
    Tạo device ID ổn định từ thông tin hardware cố định (không phụ thuộc mạng)
    Trả về: (device_id_hash, display_info, hardware_summary)
    """
    # 1. CPU ID - Thông tin quan trọng nhất (unique cho mỗi CPU)
    cpu_id = get_cpu_id()
    
    # 2. Motherboard Serial - Cố định với bo mạch chủ
    motherboard_serial = get_motherboard_serial()
    
    # 3. BIOS Serial - Thông tin BIOS
    bios_serial = get_bios_serial()
    
    # 4. Disk Serial - Serial ổ cứng chính
    disk_serial = get_primary_disk_serial()
    
    # 5. Tạo device fingerprint từ thông tin hardware cố định
    # KHÔNG sử dụng MAC address để tránh thay đổi theo mạng
    raw = f"{cpu_id}-{motherboard_serial}-{bios_serial}-{disk_serial}-{SECRET_SALT}"
    device_id_hash = hashlib.sha256(raw.encode()).hexdigest()
    
    # Thông tin hiển thị (để debug)
    display_info = f"CPU:{cpu_id[:8]}|MB:{motherboard_serial[:8]}|BIOS:{bios_serial[:8]}"
    hardware_summary = f"{cpu_id}-{motherboard_serial}-{bios_serial}-{disk_serial}"
    
    return device_id_hash, display_info, hardware_summary


def get_stable_mac_address():
    """Lấy MAC address ổn định nhất từ card mạng chính"""
    try:
        import psutil
        # Lấy tất cả network interfaces
        interfaces = psutil.net_if_addrs()
        
        # Ưu tiên các interface thật (không phải ảo)
        preferred_names = ['Ethernet', 'Wi-Fi', 'Local Area Connection', 'Wireless Network Connection']
        
        for name in preferred_names:
            for interface_name, addrs in interfaces.items():
                if name.lower() in interface_name.lower():
                    for addr in addrs:
                        if addr.family == psutil.AF_LINK and addr.address:
                            # Loại bỏ dấu '-' và ':' để chuẩn hóa
                            mac = addr.address.replace('-', '').replace(':', '').upper()
                            if mac and mac != '000000000000':
                                return mac
        
        # Fallback: lấy MAC đầu tiên không phải ảo
        for interface_name, addrs in interfaces.items():
            # Bỏ qua các interface ảo
            if any(skip in interface_name.lower() for skip in ['loopback', 'virtual', 'vmware', 'vbox', 'docker']):
                continue
            for addr in addrs:
                if addr.family == psutil.AF_LINK and addr.address:
                    mac = addr.address.replace('-', '').replace(':', '').upper()
                    if mac and mac != '000000000000':
                        return mac
    except ImportError:
        pass
    except Exception:
        pass
    
    # Fallback cuối cùng: sử dụng uuid.getnode()
    try:
        mac = format(uuid.getnode(), '012x').upper()
        return mac
    except:
        return "UNKNOWN_MAC"


def get_hardware_serial():
    """Lấy serial number từ nhiều nguồn hardware"""
    serial = "unknown"
    
    if platform.system() == "Windows":
        # Thử nhiều cách lấy serial number
        methods = [
            get_disk_serial_wmic,
            get_motherboard_serial_wmic,
            get_bios_serial_wmic,
            get_system_serial_reg
        ]
        
        for method in methods:
            try:
                result = method()
                if result and result.strip() and result.strip().lower() not in ['unknown', 'n/a', 'not available', '']:
                    serial = result.strip()
                    break
            except:
                continue
    
    return serial


def get_disk_serial_wmic():
    """Lấy disk serial bằng WMIC"""
    try:
        result = subprocess.check_output(
            "wmic diskdrive get SerialNumber /format:list", 
            shell=True, 
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        lines = result.decode('utf-8', errors='ignore').strip().split('\n')
        for line in lines:
            if 'SerialNumber=' in line:
                serial = line.split('=', 1)[1].strip()
                if serial and serial.lower() not in ['', 'n/a']:
                    return serial
    except:
        pass
    return None


def get_motherboard_serial_wmic():
    """Lấy motherboard serial bằng WMIC"""
    try:
        result = subprocess.check_output(
            "wmic baseboard get SerialNumber /format:list", 
            shell=True, 
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        lines = result.decode('utf-8', errors='ignore').strip().split('\n')
        for line in lines:
            if 'SerialNumber=' in line:
                serial = line.split('=', 1)[1].strip()
                if serial and serial.lower() not in ['', 'n/a', 'default string']:
                    return serial
    except:
        pass
    return None


def get_bios_serial_wmic():
    """Lấy BIOS serial bằng WMIC"""
    try:
        result = subprocess.check_output(
            "wmic bios get SerialNumber /format:list", 
            shell=True, 
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        lines = result.decode('utf-8', errors='ignore').strip().split('\n')
        for line in lines:
            if 'SerialNumber=' in line:
                serial = line.split('=', 1)[1].strip()
                if serial and serial.lower() not in ['', 'n/a', 'default string']:
                    return serial
    except:
        pass
    return None


def get_system_serial_reg():
    """Lấy system serial từ Windows Registry"""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS")
        serial, _ = winreg.QueryValueEx(key, "SystemSerialNumber")
        winreg.CloseKey(key)
        if serial and serial.strip().lower() not in ['', 'n/a', 'default string']:
            return serial.strip()
    except:
        pass
    return None


def get_cpu_id():
    """Lấy CPU ID - thông tin quan trọng nhất để identify máy"""
    try:
        if platform.system() == "Windows":
            result = subprocess.check_output(
                "wmic cpu get ProcessorId /format:list", 
                shell=True, 
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            lines = result.decode('utf-8', errors='ignore').strip().split('\n')
            for line in lines:
                if 'ProcessorId=' in line:
                    cpu_id = line.split('=', 1)[1].strip()
                    if cpu_id and cpu_id.lower() not in ['', 'n/a', 'unknown']:
                        return cpu_id
    except:
        pass
    
    # Fallback: sử dụng platform info
    try:
        return f"{platform.processor()}-{platform.machine()}".replace(' ', '_')
    except:
        return "UNKNOWN_CPU"


def get_motherboard_serial():
    """Lấy serial number của motherboard"""
    try:
        if platform.system() == "Windows":
            result = subprocess.check_output(
                "wmic baseboard get SerialNumber /format:list", 
                shell=True, 
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            lines = result.decode('utf-8', errors='ignore').strip().split('\n')
            for line in lines:
                if 'SerialNumber=' in line:
                    serial = line.split('=', 1)[1].strip()
                    if serial and serial.lower() not in ['', 'n/a', 'default string', 'to be filled by o.e.m.']:
                        return serial
    except:
        pass
    return "UNKNOWN_MB"


def get_bios_serial():
    """Lấy serial number của BIOS"""
    try:
        if platform.system() == "Windows":
            result = subprocess.check_output(
                "wmic bios get SerialNumber /format:list", 
                shell=True, 
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            lines = result.decode('utf-8', errors='ignore').strip().split('\n')
            for line in lines:
                if 'SerialNumber=' in line:
                    serial = line.split('=', 1)[1].strip()
                    if serial and serial.lower() not in ['', 'n/a', 'default string', 'to be filled by o.e.m.']:
                        return serial
    except:
        pass
    return "UNKNOWN_BIOS"


def get_primary_disk_serial():
    """Lấy serial number của ổ cứng chính (thường là C:)"""
    try:
        if platform.system() == "Windows":
            # Lấy serial của ổ cứng chứa Windows (thường là C:)
            result = subprocess.check_output(
                r"wmic diskdrive where \"DeviceID='\\.\PHYSICALDRIVE0'\" get SerialNumber /format:list", 
                shell=True, 
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            lines = result.decode('utf-8', errors='ignore').strip().split('\n')
            for line in lines:
                if 'SerialNumber=' in line:
                    serial = line.split('=', 1)[1].strip()
                    if serial and serial.lower() not in ['', 'n/a']:
                        return serial
            
            # Fallback: lấy serial của disk đầu tiên
            result = subprocess.check_output(
                "wmic diskdrive get SerialNumber /format:list", 
                shell=True, 
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            lines = result.decode('utf-8', errors='ignore').strip().split('\n')
            for line in lines:
                if 'SerialNumber=' in line:
                    serial = line.split('=', 1)[1].strip()
                    if serial and serial.lower() not in ['', 'n/a']:
                        return serial
    except:
        pass
    return "UNKNOWN_DISK"


def get_cpu_info():
    """Lấy thông tin CPU để tăng tính ổn định - DEPRECATED, sử dụng get_cpu_id()"""
    return get_cpu_id()


def get_motherboard_info():
    """Lấy thông tin motherboard"""
    try:
        if platform.system() == "Windows":
            result = subprocess.check_output(
                "wmic baseboard get Product,Manufacturer /format:list", 
                shell=True, 
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            lines = result.decode('utf-8', errors='ignore').strip().split('\n')
            manufacturer = ""
            product = ""
            for line in lines:
                if 'Manufacturer=' in line:
                    manufacturer = line.split('=', 1)[1].strip()
                elif 'Product=' in line:
                    product = line.split('=', 1)[1].strip()
            
            if manufacturer or product:
                return f"{manufacturer}-{product}"
    except:
        pass
    
    return "UNKNOWN_MB"


def check_key_online(key: str, api_url: str):
    device_id_hash, mac, serial = get_device_id()

    try:
        response = requests.post(api_url, data={
            "key": key,
            "device_id": device_id_hash
        }, timeout=10)

        # Nếu lỗi status HTTP (500, 404,...)
        try:
            res = response.json()
            message = res.get("message", f"❌ HTTP {response.status_code}")
        except Exception:
            message = f"❌ HTTP {response.status_code} (no JSON)"
            res = {}

        if response.status_code != 200:
            return False, message, {}
        
        
        res = response.json()

        if res.get("success"):
            info = {
                "key": key,
                "device_id": f"{mac} | {serial}",
                "expires": res.get("expires", ""),
                "remaining": res.get("remaining", "")
            }
            return True, res.get("message", "✅ Thành công"), info
        else:
            return False, res.get("message", "❌ KEY không hợp lệ"), {}

    except ConnectionError:
        return False, "📡 Không thể kết nối tới máy chủ. Kiểm tra kết nối mạng.", {}

    except Timeout:
        return False, "⏳ Máy chủ không phản hồi. Vui lòng thử lại sau.", {}

    except RequestException as e:
        return False, f"❌ Lỗi mạng: {str(e)}", {}

    except Exception as e:
        return False, f"⚠️ Lỗi không xác định: {str(e)}", {}


class KeyLoginDialog(QDialog):
    """Dialog đăng nhập sử dụng API server"""
    
    def __init__(self, api_url=""):
        super().__init__()
        self.api_url = api_url
        self.setWindowTitle("Đăng nhập qua API Server - @huyit32")
        self.validated = False
        self.key_info = {}
        
        # Set icon cho dialog
  
        
        self.setFixedWidth(450)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        self.build_ui()
    
    def build_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Tiêu đề
        title = QLabel("Đăng nhập qua API Server")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2196F3;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Mô tả
        desc = QLabel("Nhập KEY để sử dụng công cụ\nHệ thống sẽ kiểm tra qua API Server")
        desc.setStyleSheet("font-size: 12px; color: #666;")
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)
        
        # Input key
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Nhập KEY của bạn...")
        self.key_input.setMinimumHeight(35)
        self.key_input.setStyleSheet("""
            QLineEdit {
                font-size: 14px;
                padding: 8px;
                border: 2px solid #ddd;
                border-radius: 5px;
            }
            QLineEdit:focus {
                border-color: #2196F3;
            }
        """)
        self.key_input.returnPressed.connect(self.validate_key)
        layout.addWidget(self.key_input)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #ddd;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Status text
        self.status_text = QTextEdit()
        self.status_text.setMaximumHeight(80)
        self.status_text.setVisible(False)
        self.status_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 3px;
                font-size: 11px;
                background-color: #f9f9f9;
            }
        """)
        layout.addWidget(self.status_text)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        self.submit_btn = QPushButton("🔑 Xác nhận")
        self.submit_btn.setMinimumHeight(35)
        self.submit_btn.setFixedWidth(100)

        self.submit_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.submit_btn.clicked.connect(self.validate_key)
        btn_layout.addWidget(self.submit_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
        self.key_input.setFocus()
    
    def validate_key(self):
        key = self.key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Thiếu KEY", "Vui lòng nhập KEY để tiếp tục.")
            return
        
        # Disable UI
        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("⏳ Đang kiểm tra...")
        self.key_input.setEnabled(False)
        
        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
        # Show status
        self.status_text.setVisible(True)
        self.status_text.clear()
        self.status_text.append("🔄 Đang kết nối API Server...")
        
        # Start validation thread
        self.thread = KeyValidationThread(key, self.api_url)
        self.thread.result_ready.connect(self.handle_result)
        self.thread.start()
    
    def handle_result(self, success, message, info):
        # Hide progress
        self.progress_bar.setVisible(False)
        self.status_text.setVisible(False)
        
        # Re-enable UI
        self.submit_btn.setEnabled(True)
        self.submit_btn.setText("🔑 Xác nhận")
        self.submit_btn.setFixedWidth(100)
        self.key_input.setEnabled(True)
        
        if success:
            QMessageBox.information(self, "Thành công", message)
            self.validated = True
            self.key_info = info
            self.accept()
        else:
            QMessageBox.critical(self, "Thất bại", message)
            self.key_input.setFocus()
            self.key_input.selectAll()


class KeyValidationThread(QThread):
    """Thread để xác thực key qua API"""
    result_ready = pyqtSignal(bool, str, dict)
    
    def __init__(self, key, api_url):
        super().__init__()
        self.key = key
        self.api_url = api_url
    
    def run(self):
        success, message, info = check_key_online(self.key, self.api_url)
        self.result_ready.emit(success, message, info)