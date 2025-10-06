import uuid
import hashlib
import platform
import subprocess
import requests
import os
import time
import random
import socket
import hmac
from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QHBoxLayout, QSpacerItem, QSizePolicy, QProgressBar, QTextEdit, QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from requests.exceptions import RequestException, ConnectionError, Timeout

SECRET_SALT = "huydev"

# OS-specific stable IDs
def _get_windows_machine_guid():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
        val, _ = winreg.QueryValueEx(key, "MachineGuid")
        if val:
            return val.strip()
    except Exception:
        pass
    return None

def _get_macos_io_platform_uuid():
    try:
        out = subprocess.check_output(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"], stderr=subprocess.DEVNULL)
        out = out.decode(errors="ignore")
        for line in out.splitlines():
            if "IOPlatformUUID" in line:
                parts = line.split("=", 1)
                if len(parts) > 1:
                    return parts[1].strip().strip('"')
    except Exception:
        pass
    return None

def _get_linux_machine_id():
    for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            val = Path(p).read_text().strip()
            if val:
                return val
        except Exception:
            pass
    return None

def _get_fallback_storage_path():
    home = Path.home()
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA", home)
    else:
        base = os.environ.get("XDG_CONFIG_HOME", home / ".config")
    return Path(base) / "mycoolapp" / "device_id.txt"

def _get_mac_addresses():
    # best-effort: list of MACs, may include virtual ones
    try:
        import netifaces
        macs = []
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_LINK in addrs:
                for a in addrs[netifaces.AF_LINK]:
                    mac = a.get('addr')
                    if mac and len(mac) >= 11:
                        macs.append(mac)
        return macs
    except Exception:
        # fallback using uuid.getnode() (single MAC or random)
        try:
            mac_int = uuid.getnode()
            mac = format(mac_int, '012x')
            return [mac]
        except Exception:
            return []

def get_stable_device_id():
    """
    Tries multiple sources in order:
    1) OS stable ID (MachineGuid / IOPlatformUUID / machine-id)
    2) persisted UUID in app config dir
    3) derive a fingerprint from multiple best-effort sources (macs, hostname)
    Returns: (device_digest, components_dict)
    """
    comps = {}
    system = platform.system()
    comps['platform'] = system

    os_id = None
    if system == "Windows":
        os_id = _get_windows_machine_guid()
        comps['windows_machine_guid'] = os_id
    elif system == "Darwin":
        os_id = _get_macos_io_platform_uuid()
        comps['mac_io_platform_uuid'] = os_id
    else:
        os_id = _get_linux_machine_id()
        comps['linux_machine_id'] = os_id

    if os_id:
        primary = f"os:{os_id}"
    else:
        # try persisted fallback
        storage = _get_fallback_storage_path()
        try:
            persisted = storage.read_text().strip()
            if persisted:
                primary = f"persisted:{persisted}"
                comps['persisted_path'] = str(storage)
                comps['persisted_value'] = persisted
            else:
                raise FileNotFoundError
        except Exception:
            # generate and persist
            new_uuid = str(uuid.uuid4())
            try:
                storage.parent.mkdir(parents=True, exist_ok=True)
                storage.write_text(new_uuid)
                primary = f"persisted:{new_uuid}"
                comps['persisted_path'] = str(storage)
                comps['persisted_value'] = new_uuid
            except Exception:
                # ultimate fallback
                primary = f"fallback:{str(uuid.uuid4())}"

    # gather auxiliary (best-effort) data but not relied as single source
    macs = _get_mac_addresses()
    comps['macs'] = macs
    comps['hostname'] = platform.node()

    # combine a few fields to make fingerprint more robust
    # note: do NOT trust macs alone; they are auxiliary
    raw = "|".join([primary, comps.get('hostname',"")] + macs[:2])
    # produce HMAC-SHA256 as irreversible digest
    digest = hmac.new(SECRET_SALT.encode(), raw.encode(), hashlib.sha256).hexdigest()

    comps['raw_for_hash'] = raw
    comps['device_digest'] = digest
    return digest, comps

def get_device_id():
    """Backward compatibility wrapper"""
    device_digest, comps = get_stable_device_id()
    # Return format compatible with old code: (hash, mac, serial)
    mac = comps.get('macs', ['unknown'])[0] if comps.get('macs') else 'unknown'
    serial = comps.get('windows_machine_guid', comps.get('mac_io_platform_uuid', 'unknown'))
    return device_digest, mac, serial

def get_unique_device_id():
    """Wrapper for get_stable_device_id with compatible return format"""
    device_digest, comps = get_stable_device_id()
    # Return format: (device_id_hash, display_info, hardware_summary)
    display_info = f"Platform: {comps.get('platform', 'unknown')}"
    hardware_summary = f"OS ID: {comps.get('windows_machine_guid', comps.get('mac_io_platform_uuid', comps.get('linux_machine_id', 'unknown')))}"
    return device_digest, display_info, hardware_summary


def check_key_online(key: str, api_url: str):
    device_id_hash, display_info, hardware_summary = get_unique_device_id()

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
                "device_id": display_info,
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
        self.remember_key = True  # Mặc định là lưu key
        
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
        
        # Checkbox lưu key
        self.remember_key_checkbox = QCheckBox("Lưu key để không phải nhập lại lần sau")
        self.remember_key_checkbox.setChecked(True)  # Mặc định là lưu
        self.remember_key_checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 12px;
                color: #555;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #ddd;
                border-radius: 3px;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #2196F3;
                border-radius: 3px;
                background-color: #2196F3;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEwIDNMNC41IDguNUwyIDYiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPgo=);
            }
        """)
        layout.addWidget(self.remember_key_checkbox)
        
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
            self.remember_key = self.remember_key_checkbox.isChecked()  # Lưu trạng thái checkbox
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