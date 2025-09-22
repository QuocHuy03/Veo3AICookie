import logging
import sys
import os
import requests
import zipfile
import io
import time
import subprocess
import platform

# Constants
DOWNLOAD_TIMEOUT = 15
APP_STARTUP_DELAY = 2
MAIN_APP_NAME = "Veo3AI.exe"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def download_and_replace(url):
    """
    Download and replace application files
    
    Args:
        url: URL to download the update zip file
    """
    try:
        logger.info("Starting update process...")
        
        # Download update file
        zip_content = _download_update_file(url)
        if not zip_content:
            return
            
        # Extract and replace files
        _extract_and_replace_files(zip_content)
        
        # Restart application
        _restart_application()
        
    except Exception as e:
        logger.error(f"Update failed: {e}")
        

def _download_update_file(url):
    """
    Download update file from URL
    
    Args:
        url: Download URL
        
    Returns:
        bytes: Zip file content or None if failed
    """
    try:
        logger.info("Downloading update file...")
        response = requests.get(url, timeout=DOWNLOAD_TIMEOUT)
        response.raise_for_status()
        
        logger.info("Download completed successfully")
        return response.content
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Download failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during download: {e}")
        return None


def _extract_and_replace_files(zip_content):
    """
    Extract and replace application files
    
    Args:
        zip_content: Zip file content as bytes
    """
    try:
        logger.info("Extracting and replacing files...")
        
        with zipfile.ZipFile(io.BytesIO(zip_content)) as zip_file:
            zip_file.extractall(path=os.getcwd())
            
        logger.info("Files extracted and replaced successfully")
        
    except zipfile.BadZipFile as e:
        logger.error(f"Invalid zip file: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to extract files: {e}")
        raise


def _restart_application():
    """Restart the main application"""
    try:
        logger.info("Restarting application...")
        
        app_path = os.path.join(os.getcwd(), MAIN_APP_NAME)
        
        if os.path.exists(app_path):
            # Ẩn cửa sổ CMD trên Windows
            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                
            subprocess.Popen([app_path], startupinfo=startupinfo)
            logger.info("Application restarted successfully")
        else:
            logger.error(f"Main application not found: {app_path}")
            
    except Exception as e:
        logger.error(f"Failed to restart application: {e}")


def main():
    """Main updater entry point"""
    if len(sys.argv) < 2:
        logger.error("Missing download URL argument")
        sys.exit(1)

    download_url = sys.argv[1]
    logger.info(f"Updater started with URL: {download_url}")
    
    # Wait for main app to exit
    time.sleep(APP_STARTUP_DELAY)
    
    # Perform update
    download_and_replace(download_url)


if __name__ == "__main__":
    main()