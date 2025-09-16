import logging
import requests
import subprocess
import sys
import os
import platform
from PyQt5.QtWidgets import QMessageBox
from packaging import version

# Constants
CURRENT_VERSION = "1.0.0"  # 👉 Cập nhật version tại đây
REQUEST_TIMEOUT = 5
UPDATER_SCRIPT = "updater.py"
MAIN_APP = "MakeVideoAI.exe"

# Configure logging
logger = logging.getLogger(__name__)


def check_for_update(version_url):
    """
    Check for available updates
    
    Args:
        version_url: URL to version information JSON
        
    Returns:
        bool: True if update was applied, False otherwise
    """
    try:
        response = _fetch_version_info(version_url)
        if not response:
            return False

        latest_version, changelog, download_url = _parse_version_response(response)
        
        if _is_new_version_available(latest_version):
            return _show_update_prompt(latest_version, changelog, download_url)
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking for updates: {e}")
        return False


def _fetch_version_info(version_url):
    """Fetch version information from server"""
    try:
        response = requests.get(version_url, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            logger.warning(f"Version check failed with status {response.status_code}")
            return None
        return response
    except Exception as e:
        logger.error(f"Failed to fetch version info: {e}")
        return None


def _parse_version_response(response):
    """Parse version response data"""
    try:
        data = response.json()
        latest_version = data.get("version", "").strip()
        changelog = data.get("changelog", "Không có mô tả cập nhật.")
        download_url = data.get("download_url", "")
        
        return latest_version, changelog, download_url
        
    except Exception as e:
        logger.error(f"Failed to parse version response: {e}")
        return "", "", ""


def _is_new_version_available(latest_version):
    """Check if a new version is available"""
    try:
        return version.parse(latest_version) > version.parse(CURRENT_VERSION)
    except Exception as e:
        logger.error(f"Version comparison failed: {e}")
        return False


def _show_update_prompt(latest_version, changelog, download_url):
    """
    Show update prompt to user
    
    Args:
        latest_version: Latest available version
        changelog: Update changelog
        download_url: Download URL for update
        
    Returns:
        bool: True if update was initiated, False otherwise
    """
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Information)
    msg.setWindowTitle(f"🔔 Cập nhật mới ({latest_version})")
    msg.setText(f"<b>Motion Video Pro</b> đã có bản mới <b>{latest_version}</b>!")
    msg.setInformativeText("Bạn có muốn tải bản mới không?")
    msg.setDetailedText(changelog)
    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msg.setDefaultButton(QMessageBox.Yes)

    if msg.exec_() == QMessageBox.Yes:
        if download_url:
            return _launch_updater(download_url)
        else:
            logger.warning("No download URL provided for update")
            return False
    
    return False


def _launch_updater(download_url):
    """
    Launch the updater script
    
    Args:
        download_url: URL to download the update
        
    Returns:
        bool: True if updater was launched successfully
    """
    try:
        updater_path = os.path.join(os.getcwd(), UPDATER_SCRIPT)
        
        if not os.path.exists(updater_path):
            logger.error(f"Updater script not found: {updater_path}")
            return False
            
        # Ẩn cửa sổ CMD trên Windows
        startupinfo = None
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
        subprocess.Popen([sys.executable, updater_path, download_url], startupinfo=startupinfo)
        logger.info("Updater launched successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to launch updater: {e}")
        return False