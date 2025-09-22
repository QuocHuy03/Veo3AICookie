import sys
import os
import json
import re
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, 
                             QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QLabel, QLineEdit, 
                             QTextEdit, QComboBox, QSpinBox, QFileDialog, QMessageBox,
                             QDialog, QFormLayout, QGroupBox,
                             QProgressBar, QCheckBox, QFrame)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
import pandas as pd
import requests
from api import *

def create_styled_messagebox(parent, title, message, icon=QMessageBox.Information):
    """Tạo QMessageBox với styling đơn giản"""
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.setIcon(icon)
    msg.setStyleSheet("""
        QMessageBox {
            background-color: white;
            font-family: "Segoe UI";
            font-size: 12px;
        }
        QMessageBox QPushButton {
            background-color: #007bff;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
            min-width: 80px;
        }
        QMessageBox QPushButton:hover {
            background-color: #0056b3;
        }
    """)
    return msg

class ProcessingResultDialog(QDialog):
    """Dialog hiển thị kết quả xử lý video chuyên nghiệp"""
    def __init__(self, results, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kết quả xử lý Video")
        self.setModal(True)
        self.resize(600, 500)
        
        self.results = results
        self.parent_window = parent
        successful = [r for r in results if r[2]]
        failed = [r for r in results if not r[2]]
        
        self.init_ui(successful, failed, results)
        
    def init_ui(self, successful, failed, all_results):
        layout = QVBoxLayout()
        
        # Header với icon và title
        header_layout = QHBoxLayout()
        
        # Icon success/failure
        icon_label = QLabel()
        if len(failed) == 0:
            icon_label.setText("✅")
            icon_label.setStyleSheet("font-size: 48px; color: #28a745;")
        else:
            icon_label.setText("⚠️")
            icon_label.setStyleSheet("font-size: 48px; color: #ffc107;")
        
        header_layout.addWidget(icon_label)
        
        # Title và stats
        title_layout = QVBoxLayout()
        title_label = QLabel("Xử lý Video Hoàn thành!")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #333;
            }
        """)
        title_layout.addWidget(title_label)
        
        stats_label = QLabel(f"📊 Thành công: {len(successful)} | ❌ Thất bại: {len(failed)}")
        stats_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #666;
            }
        """)
        title_layout.addWidget(stats_label)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Progress bar tổng quan
        progress_frame = QFrame()
        progress_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 10px;
                margin: 10px 0;
            }
        """)
        progress_layout = QVBoxLayout()
        
        progress_label = QLabel("Tiến độ hoàn thành:")
        progress_label.setStyleSheet("font-weight: bold; color: #333;")
        progress_layout.addWidget(progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, len(all_results))
        self.progress_bar.setValue(len(successful))
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #e0e0e0;
                border-radius: 5px;
                text-align: center;
                background-color: white;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 3px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        progress_frame.setLayout(progress_layout)
        layout.addWidget(progress_frame)
        
        # Chi tiết kết quả
        details_group = QGroupBox("Chi tiết kết quả")
        details_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                font-family: "Roboto", "Open Sans", "Segoe UI";
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        details_layout = QVBoxLayout()
        
        # Scrollable results
        scroll_area = QTextEdit()
        scroll_area.setReadOnly(True)
        scroll_area.setMaximumHeight(150)
        scroll_area.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                background-color: white;
                font-family: "Roboto", "Open Sans", "Segoe UI";
                font-size: 12px;
                padding: 5px;
            }
        """)
        
        # Add results to text area
        result_text = ""
        for stt, prompt, success, result in all_results:
            if success:
                result_text += f"✅ STT {stt}: {result}\n"
            else:
                result_text += f"❌ STT {stt}: {result}\n"
        
        scroll_area.setPlainText(result_text)
        details_layout.addWidget(scroll_area)
        
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Nút Chạy lại cho các video thất bại
        if len(failed) > 0:
            self.retry_btn = QPushButton(f"🔄 Chạy lại {len(failed)} video thất bại")
            self.retry_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffc107;
                    color: #212529;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 5px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #e0a800;
                }
            """)
            self.retry_btn.clicked.connect(self.retry_failed_videos)
            button_layout.addWidget(self.retry_btn)
        
        button_layout.addStretch()
        
        self.close_btn = QPushButton("Đóng")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Set dialog style
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                border-radius: 10px;
            }
        """)
    
    def retry_failed_videos(self):
        """Chạy lại các video thất bại"""
        failed_videos = [r for r in self.results if not r[2]]
        
        if not failed_videos:
            create_styled_messagebox(self, "Thông báo", "Không có video nào thất bại để chạy lại!", QMessageBox.Information).exec_()
            return
        
        # Xác nhận với người dùng
        msg = QMessageBox(self)
        msg.setWindowTitle("Xác nhận")
        msg.setText(f"Bạn có chắc chắn muốn chạy lại {len(failed_videos)} video thất bại?")
        msg.setInformativeText("Hệ thống sẽ sử dụng cùng cấu hình và tài khoản để xử lý lại.")
        msg.setIcon(QMessageBox.Question)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)
        
        if msg.exec_() == QMessageBox.Yes:
            # Đóng dialog hiện tại
            self.accept()
            
            # Gọi hàm retry từ parent window
            if self.parent_window and hasattr(self.parent_window, 'retry_failed_videos'):
                self.parent_window.retry_failed_videos(failed_videos)

class VideoMergeThread(QThread):
    """Thread để ghép video không block UI"""
    progress_updated = pyqtSignal(int, str)  # progress, message
    log_updated = pyqtSignal(str)  # log message
    finished = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, video_paths, output_path, mute_audio=False):
        super().__init__()
        self.video_paths = video_paths
        self.output_path = output_path
        self.mute_audio = mute_audio
        
    def _check_audio_streams(self):
        """Check if all videos have audio streams"""
        import subprocess
        import platform
        
        startupinfo = None
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
        
        for video_path in self.video_paths:
            try:
                # Use ffprobe to check streams
                cmd = ["ffprobe", "-v", "quiet", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", video_path]
                result = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo)
                
                # If no audio streams found, return False
                if not result.stdout.strip():
                    return False
            except:
                # If ffprobe fails, assume no audio for safety
                return False
        
        return True
        
    def run(self):
        try:
            self.log_updated.emit(f"🚀 Bắt đầu ghép {len(self.video_paths)} video (không có transition)...")
            self.progress_updated.emit(10, "Đang chuẩn bị...")
            
            # Validate video files exist
            for i, video_path in enumerate(self.video_paths):
                if not os.path.exists(video_path):
                    self.log_updated.emit(f"❌ Video {i+1} không tồn tại: {video_path}")
                    self.finished.emit(False, f"Video {i+1} không tồn tại: {video_path}")
                    return
            
            self.log_updated.emit("✅ Tất cả video files hợp lệ")
            self.progress_updated.emit(20, "Đang chuẩn bị FFmpeg...")
            
            # Check if all videos have audio streams (for better error handling)
            has_audio_streams = self._check_audio_streams()
            
            # Build FFmpeg command - always no transitions for clean merging
            cmd = ["ffmpeg", "-y"]  # -y để overwrite output file
            
            # Add input files
            for video_path in self.video_paths:
                cmd.extend(["-i", video_path])
            
            # Add filter complex for concatenation with better error handling
            if self.mute_audio or not has_audio_streams:
                # Only video concatenation, no audio
                self.log_updated.emit("🔇 Ghép video không có âm thanh")
                filter_parts = []
                for i in range(len(self.video_paths)):
                    filter_parts.append(f"[{i}:v]")
                
                video_filter = f"{''.join(filter_parts)}concat=n={len(self.video_paths)}:v=1:a=0[outv]"
                cmd.extend(["-filter_complex", video_filter])
                cmd.extend(["-map", "[outv]"])
            else:
                # Both video and audio concatenation
                self.log_updated.emit("🔊 Ghép video có âm thanh")
                filter_parts = []
                for i in range(len(self.video_paths)):
                    filter_parts.append(f"[{i}:v][{i}:a]")
                
                filter_complex = f"{''.join(filter_parts)}concat=n={len(self.video_paths)}:v=1:a=1[outv][outa]"
                cmd.extend(["-filter_complex", filter_complex])
                cmd.extend(["-map", "[outv]", "-map", "[outa]"])
            
            # Output settings with better compatibility - optimized for clean merging
            cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "23"])
            if not self.mute_audio and has_audio_streams:
                cmd.extend(["-c:a", "aac", "-b:a", "128k"])
            
            cmd.append(self.output_path)
            
            self.log_updated.emit("📝 Command: ********************************")
            self.progress_updated.emit(30, "Đang ghép video...")
            
            # Execute FFmpeg with fallback mechanism
            import subprocess
            import platform
            
            # Ẩn cửa sổ CMD trên Windows
            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            
            # Try the first command
            self.log_updated.emit(f"🔧 Đang chạy FFmpeg command...")
            result = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo)
            
            # Debug logging
            self.log_updated.emit(f"🔍 FFmpeg return code: {result.returncode}")
            self.log_updated.emit(f"🔍 FFmpeg stderr length: {len(result.stderr) if result.stderr else 0}")
            self.log_updated.emit(f"🔍 FFmpeg stdout length: {len(result.stdout) if result.stdout else 0}")
            
            # If failed and not muted audio, try video-only fallback
            if result.returncode != 0 and not self.mute_audio and has_audio_streams:
                self.log_updated.emit("⚠️ Thử lại với video-only (bỏ qua audio)...")
                
                # Build fallback command (video only)
                cmd_fallback = ["ffmpeg", "-y"]
                for video_path in self.video_paths:
                    cmd_fallback.extend(["-i", video_path])
                
                # Video-only concatenation
                filter_parts = []
                for i in range(len(self.video_paths)):
                    filter_parts.append(f"[{i}:v]")
                
                video_filter = f"{''.join(filter_parts)}concat=n={len(self.video_paths)}:v=1:a=0[outv]"
                cmd_fallback.extend(["-filter_complex", video_filter])
                cmd_fallback.extend(["-map", "[outv]"])
                cmd_fallback.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "23"])
                cmd_fallback.append(self.output_path)
                
                result = subprocess.run(cmd_fallback, capture_output=True, text=True, startupinfo=startupinfo)
            
            if result.returncode == 0:
                self.progress_updated.emit(100, "Hoàn thành!")
                self.log_updated.emit("✅ Ghép video thành công!")
                self.finished.emit(True, f"Đã ghép video thành công!\nFile: {self.output_path}")
            else:
                # Extract meaningful error from FFmpeg output
                stderr_text = result.stderr if result.stderr else ""
                stdout_text = result.stdout if result.stdout else ""
                
                error_lines = stderr_text.split('\n') if stderr_text else []
                meaningful_error = ""
                
                for line in error_lines:
                    if any(keyword in line.lower() for keyword in ['error', 'failed', 'invalid', 'cannot']):
                        meaningful_error += line + "\n"
                
                if not meaningful_error:
                    # Try to get error from stdout if stderr is empty
                    if stdout_text:
                        stdout_lines = stdout_text.split('\n')
                        for line in stdout_lines:
                            if any(keyword in line.lower() for keyword in ['error', 'failed', 'invalid', 'cannot']):
                                meaningful_error += line + "\n"
                    
                    if not meaningful_error:
                        meaningful_error = stderr_text[:300] + "..." if stderr_text else "Lỗi không xác định từ FFmpeg"
                
                self.log_updated.emit(f"❌ Lỗi ghép video: {meaningful_error[:200]}...")
                self.finished.emit(False, f"Lỗi ghép video:\n{meaningful_error}")
                
        except FileNotFoundError:
            self.log_updated.emit("❌ Không tìm thấy FFmpeg!")
            self.finished.emit(False, "Không tìm thấy FFmpeg! Vui lòng cài đặt FFmpeg.")
        except Exception as e:
            error_msg = str(e) if e else "Lỗi không xác định"
            self.log_updated.emit(f"❌ Lỗi: {error_msg}")
            self.finished.emit(False, f"Lỗi: {error_msg}")

class AddCookieDialog(QDialog):
    """Dialog để thêm cookie mới"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Cookie")
        self.setModal(True)
        self.resize(600, 500)
        self.expires_data = "Unknown"  # Khởi tạo expires data
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
                font-family: "Segoe UI";
            }
            QLabel {
                color: #333;
                font-weight: bold;
                font-size: 12px;
                margin-bottom: 5px;
            }
            QLineEdit, QTextEdit {
                padding: 8px;
                border: 2px solid #e0e0e0;
                border-radius: 5px;
                background-color: white;
                font-size: 12px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: #2196F3;
            }
            QPushButton {
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton#testBtn {
                background-color: #4CAF50;
                color: white;
            }
            QPushButton#testBtn:hover {
                background-color: #45a049;
            }
            QPushButton#okBtn {
                background-color: #2196F3;
                color: white;
            }
            QPushButton#okBtn:hover {
                background-color: #1976D2;
            }
            QPushButton#cancelBtn {
                background-color: #f5f5f5;
                color: #666;
                border: 1px solid #ddd;
            }
        """)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header_label = QLabel("🔐 Thêm Tài khoản Mới")
        header_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: bold;
                color: #2196F3;
                margin-bottom: 5px;
                padding: 5px;
                background-color: white;
                border-radius: 5px;
                border-left: 3px solid #2196F3;
            }
        """)
        layout.addWidget(header_label)
        
        # Form layout
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        form_layout.setLabelAlignment(Qt.AlignLeft)
        
        # Account name field
        name_label = QLabel("Account Name:")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nhập tên tài khoản (ví dụ: Account 1)")
        form_layout.addRow(name_label, self.name_edit)
        
        # Cookie field
        cookie_label = QLabel("Cookie:")
        self.cookie_edit = QTextEdit()
        self.cookie_edit.setPlaceholderText("Dán cookie từ trình duyệt vào đây...\n\nHướng dẫn:\n1. Mở Developer Tools (F12)\n2. Vào tab Application/Storage\n3. Copy cookie từ domain labs.google.com")
        form_layout.addRow(cookie_label, self.cookie_edit)
        
        layout.addLayout(form_layout)
        
        # Test section
        test_layout = QHBoxLayout()
        self.test_btn = QPushButton("Kiểm tra Cookie")
        self.test_btn.setObjectName("testBtn")
        self.test_btn.clicked.connect(self.test_cookie)
        test_layout.addWidget(self.test_btn)
        test_layout.addStretch()
        
        layout.addLayout(test_layout)
        
        # Status section
        self.status_label = QLabel("⏳ Chưa kiểm tra")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 12px;
                padding: 8px 12px;
                background-color: #f0f0f0;
                border-radius: 6px;
                border-left: 3px solid #999;
            }
        """)
        layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.clicked.connect(self.reject)
        
        ok_btn = QPushButton("Add")
        ok_btn.setObjectName("okBtn")
        ok_btn.clicked.connect(self.accept)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def test_cookie(self):
        """Kiểm tra cookie có hợp lệ không"""
        cookie_text = self.cookie_edit.toPlainText().strip()
        if not cookie_text:
            self.status_label.setText("Vui lòng nhập cookie")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #c62828;
                    font-size: 12px;
                    padding: 8px 12px;
                    background-color: #ffebee;
                    border-radius: 6px;
                    border-left: 3px solid #f44336;
                }
            """)
            return
            
        # Disable button và hiển thị đang xử lý
        self.test_btn.setEnabled(False)
        self.test_btn.setText("⏳ Đang xử lý...")
        self.status_label.setText("Đang kiểm tra cookie...")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #1976d2;
                font-size: 12px;
                padding: 8px 12px;
                background-color: #e3f2fd;
                border-radius: 6px;
                border-left: 3px solid #2196f3;
            }
        """)
            
        try:
            # Test cookie bằng cách gọi session API
            headers = {
                "Accept": "application/json",
                "Cookie": cookie_text,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get("https://labs.google/fx/api/auth/session", 
                                  headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                user_info = data.get("user", {})
                user_name = user_info.get("name", "Unknown")
                user_email = user_info.get("email", "Unknown")
                
                # Lấy thời gian expires
                expires_str = data.get("expires", "")
                expires_display = "Unknown"
                if expires_str:
                    try:
                        # Parse thời gian UTC
                        utc_time = datetime.fromisoformat(expires_str.replace('Z', '+00:00'))
                        # Chuyển sang giờ Việt Nam (UTC+7)
                        from datetime import timezone, timedelta
                        vn_time = utc_time.astimezone(timezone(timedelta(hours=7)))
                        # Format theo định dạng Việt Nam
                        expires_display = vn_time.strftime("%d/%m/%Y %H:%M:%S")
                    except:
                        expires_display = expires_str
                
                self.status_label.setText(f"Done - {user_name} ({user_email})")
                self.status_label.setStyleSheet("""
                    QLabel {
                        color: #2e7d32;
                        font-size: 12px;
                        padding: 8px 12px;
                        background-color: #e8f5e8;
                        border-radius: 6px;
                        border-left: 3px solid #4caf50;
                    }
                """)
                
                # Auto fill name if empty
                if not self.name_edit.text():
                    self.name_edit.setText(user_name)
                    
                # Enable button và reset text
                self.test_btn.setEnabled(True)
                self.test_btn.setText("Kiểm tra Cookie")
                
                # Lưu expires vào data để hiển thị trong table
                self.expires_data = expires_display
                    
                if "email" in cookie_text.lower():
                    print(f"Debug - Found 'email' in cookie")
                else:
                    print(f"Debug - No 'email' found in cookie")
                    
            else:
                self.status_label.setText(f"Error HTTP {response.status_code}")
                self.status_label.setStyleSheet("""
                    QLabel {
                        color: #c62828;
                        font-size: 12px;
                        padding: 8px 12px;
                        background-color: #ffebee;
                        border-radius: 6px;
                        border-left: 3px solid #f44336;
                    }
                """)
                
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #c62828;
                    font-size: 12px;
                    padding: 8px 12px;
                    background-color: #ffebee;
                    border-radius: 6px;
                    border-left: 3px solid #f44336;
                }
            """)
            
        finally:
            # Luôn enable lại button và reset text
            self.test_btn.setEnabled(True)
            self.test_btn.setText("Kiểm tra Cookie")
    
    def get_data(self):
        """Lấy dữ liệu từ dialog"""
        return {
            "name": self.name_edit.text().strip(),
            "cookie": self.cookie_edit.toPlainText().strip(),
            "status": self.status_label.text(),
            "expires": getattr(self, 'expires_data', 'Unknown'),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

class VideoProcessingThread(QThread):
    """Thread để xử lý video không block UI với parallel processing và auto account distribution"""
    progress_updated = pyqtSignal(int, str)  # progress, message
    status_updated = pyqtSignal(str)  # status message for log
    finished = pyqtSignal(list)  # results
    
    def __init__(self, prompts, accounts_data, config, max_workers=3):
        super().__init__()
        self.prompts = prompts
        self.accounts_data = accounts_data  # Changed to support multiple accounts
        self.config = config
        self.max_workers = max_workers
        self.processed_count = 0
        self.total_count = len(prompts)
        self.current_account_index = 0  # For account rotation
        
        # Tối ưu hóa: Chia đều prompts cho các tài khoản
        self.account_prompts_distribution = self.distribute_prompts_to_accounts()
        
        # Tối ưu: Connection pooling và timeout settings
        self.session_config = {
            'timeout': (10, 30),  # Connect timeout, read timeout
            'max_retries': 3,
            'backoff_factor': 0.3
        }
        
        # Thêm flag để kiểm soát việc dừng
        self.should_stop = False
        self.executor = None
    
    def stop_processing(self):
        """Dừng quá trình xử lý"""
        self.should_stop = True
        if self.executor:
            self.executor.shutdown(wait=False)
        
    def distribute_prompts_to_accounts(self):
        """Chia đều prompts cho các tài khoản để tối ưu hóa"""
        if not self.accounts_data or not self.prompts:
            return {}
        
        account_count = len(self.accounts_data)
        prompt_count = len(self.prompts)
        
        # Tối ưu: Sử dụng generator để tiết kiệm memory
        prompts_per_account = prompt_count // account_count
        remaining_prompts = prompt_count % account_count
        
        distribution = {}
        start_index = 0
        
        for i, account in enumerate(self.accounts_data):
            account_name = account.get("name", f"Account {i+1}")
            
            # Tài khoản đầu tiên sẽ nhận thêm các prompts còn lại
            prompts_for_this_account = prompts_per_account + (1 if i < remaining_prompts else 0)
            
            end_index = start_index + prompts_for_this_account
            # Tối ưu: Chỉ lưu indices thay vì copy toàn bộ data
            account_prompts = self.prompts[start_index:end_index]
            
            distribution[account_name] = {
                'account': account,
                'prompts': account_prompts,
                'count': len(account_prompts),
                'start_idx': start_index,
                'end_idx': end_index
            }
            
            start_index = end_index
        
        return distribution
        
    def get_next_account(self):
        """Lấy tài khoản tiếp theo để xoay vòng"""
        if not self.accounts_data:
            return None
        
        account = self.accounts_data[self.current_account_index]
        self.current_account_index = (self.current_account_index + 1) % len(self.accounts_data)
        return account
    
    def process_single_video(self, prompt_data):
        """Xử lý một video đơn lẻ với auto account rotation"""
        stt, prompt, image_path = prompt_data
        
        print(f"DEBUG: STT {stt} - Processing video")
        print(f"DEBUG: STT {stt} - Image path: {image_path}")
        print(f"DEBUG: STT {stt} - Image exists: {image_path and os.path.exists(image_path) if image_path else False}")
        
        try:
            # Lấy tài khoản tiếp theo để xoay vòng
            account_data = self.get_next_account()
            if not account_data:
                return (stt, prompt, False, "Không có tài khoản nào khả dụng")
            
            # Lấy token từ cookie của tài khoản được chọn
            cookie_header_value = account_data["cookie"]
            account_name = account_data.get("name", "Unknown")
            
            # Kiểm tra cookie có hợp lệ không
            if not cookie_header_value or cookie_header_value.startswith("YOUR_COOKIE_HERE"):
                return (stt, prompt, False, f"Cookie không hợp lệ cho {account_name}")
            
            token = fetch_access_token_from_session(cookie_header_value)
            
            if not token:
                return (stt, prompt, False, f"Không thể lấy token từ {account_name} - Cookie có thể đã hết hạn")
            
            # Tạo output filename
            output_filename = create_short_filename(stt, prompt)
            output_path = os.path.join(self.config["output_dir"], output_filename)
            
            # Generate video - Auto-select model based on image presence and aspect ratio
            if image_path and os.path.exists(image_path):
                print("Vào video rồi nè cu hề")
                # Image-to-video: Select model based on aspect ratio
                if self.config["aspect_ratio"] == "VIDEO_ASPECT_RATIO_PORTRAIT":
                    model_key = "veo_3_i2v_s_fast_portrait_ultra"
                else:  # LANDSCAPE
                    model_key = "veo_3_i2v_s_fast_ultra"
                    
                self.status_updated.emit(f"STT {stt}: 📤 Uploading image...")
                media_id = upload_image(token, image_path)
                self.status_updated.emit(f"STT {stt}: 🎬 Generating video from image...")
                gen_resp, scene_id = generate_video_from_image(
                    token, prompt, media_id, 
                    self.config["project_id"], 
                    model_key,
                    self.config["aspect_ratio"]
                )
            else:
                print("Vào text rồi nè cu hề")
                # Text-to-video: Select model based on aspect ratio
                if self.config["aspect_ratio"] == "VIDEO_ASPECT_RATIO_PORTRAIT":
                    model_key = "veo_3_0_t2v_fast_portrait_ultra"
                else:  # LANDSCAPE
                    model_key = "veo_3_0_t2v_fast_ultra"
                    
                self.status_updated.emit(f"STT {stt}: 🎬 Generating video...")
                gen_resp, scene_id = generate_video(
                    token, prompt, 
                    self.config["project_id"], 
                    model_key,
                    self.config["aspect_ratio"]
                )
            
            # Poll status - sử dụng hàm poll_status từ main.py
            op_name = extract_op_name(gen_resp)
            self.status_updated.emit(f"STT {stt}: ⏳ Checking generation status...")
            
            try:
                # poll_status sẽ tự động poll cho đến khi SUCCESSFUL hoặc FAILED
                status_resp = poll_status(token, op_name, scene_id, interval_sec=2.0, timeout_sec=600)
                self.status_updated.emit(f"STT {stt}: ✅ Status: SUCCESSFUL - Thành công, đang tải...")
            except RuntimeError as e:
                self.status_updated.emit(f"STT {stt}: ❌ Status: FAILED - Thất bại!")
                return (stt, prompt, False, f"Generation failed: {str(e)}")
            except TimeoutError as e:
                self.status_updated.emit(f"STT {stt}: ⏰ Timeout - Hết thời gian chờ!")
                return (stt, prompt, False, f"Timeout: {str(e)}")
            except Exception as e:
                self.status_updated.emit(f"STT {stt}: ❌ Lỗi polling: {str(e)}")
                return (stt, prompt, False, f"Polling error: {str(e)}")
            
            # Download video
            self.status_updated.emit(f"STT {stt}: 📥 Downloading video...")
            fife_url = extract_fife_url(status_resp)
            http_download_mp4(fife_url, output_path)
            
            self.status_updated.emit(f"STT {stt}: ✅ Hoàn thành: {output_filename}")
            return (stt, prompt, True, output_filename)
            
        except Exception as e:
            self.status_updated.emit(f"STT {stt}: ❌ Lỗi: {str(e)}")
            return (stt, prompt, False, str(e))
    
    def process_video_with_specific_account(self, prompt_data, account_data):
        """Xử lý video với tài khoản cụ thể (cho thuật toán chia tải tối ưu)"""
        stt, prompt, image_path = prompt_data
        account_name = account_data.get("name", "Unknown")
        
        # Kiểm tra should_stop ngay từ đầu
        if self.should_stop:
            return (stt, prompt, False, "Đã dừng bởi người dùng")
        
        try:
            # Lấy token từ cookie của tài khoản được chỉ định
            cookie_header_value = account_data["cookie"]
            
            # Kiểm tra cookie có hợp lệ không
            if not cookie_header_value or cookie_header_value.startswith("YOUR_COOKIE_HERE"):
                return (stt, prompt, False, f"Cookie không hợp lệ cho {account_name}")
            
            # Tối ưu: Cache token để tránh gọi API nhiều lần
            cache_key = f"token_{hash(cookie_header_value)}"
            if not hasattr(self, 'token_cache'):
                self.token_cache = {}
            
            token = self.token_cache.get(cache_key)
            if not token:
                token = fetch_access_token_from_session(cookie_header_value)
                if token:
                    self.token_cache[cache_key] = token
                else:
                    return (stt, prompt, False, f"Không thể lấy token từ {account_name} - Cookie có thể đã hết hạn")
            
            # Tạo output filename
            output_filename = create_short_filename(stt, prompt)
            output_path = os.path.join(self.config["output_dir"], output_filename)
            
            # Generate video - Auto-select model based on image presence
            if image_path and os.path.exists(image_path):
                # Kiểm tra should_stop trước khi upload
                if self.should_stop:
                    return (stt, prompt, False, "Đã dừng bởi người dùng")
                
                # Image-to-video: Select model based on aspect ratio
                if self.config["aspect_ratio"] == "VIDEO_ASPECT_RATIO_PORTRAIT":
                    model_key = "veo_3_i2v_s_fast_portrait_ultra"
                else:  # LANDSCAPE
                    model_key = "veo_3_i2v_s_fast_ultra"
                    
                self.status_updated.emit(f"STT {stt}: 📤 Uploading image với {account_name}...")
                media_id = upload_image(token, image_path)
                
                # Kiểm tra should_stop sau khi upload
                if self.should_stop:
                    return (stt, prompt, False, "Đã dừng bởi người dùng")
                
                self.status_updated.emit(f"STT {stt}: 🎬 Generating video from image với {account_name}...")
                gen_resp, scene_id = generate_video_from_image(
                    token, prompt, media_id, 
                    self.config["project_id"], 
                    model_key,
                    self.config["aspect_ratio"]
                )
            else:
                # Kiểm tra should_stop trước khi generate
                if self.should_stop:
                    return (stt, prompt, False, "Đã dừng bởi người dùng")
                
                # Text-to-video: Select model based on aspect ratio
                if self.config["aspect_ratio"] == "VIDEO_ASPECT_RATIO_PORTRAIT":
                    model_key = "veo_3_0_t2v_fast_portrait_ultra"
                else:  # LANDSCAPE
                    model_key = "veo_3_0_t2v_fast_ultra"
                    
                self.status_updated.emit(f"STT {stt}: 🎬 Generating video với {account_name}...")
                gen_resp, scene_id = generate_video(
                    token, prompt, 
                    self.config["project_id"], 
                    model_key,
                    self.config["aspect_ratio"]
                )
            
            # Poll status với retry logic tối ưu
            op_name = extract_op_name(gen_resp)
            self.status_updated.emit(f"STT {stt}: ⏳ Checking generation status với {account_name}...")
            
            # Tối ưu: Retry với exponential backoff
            max_retries = 3
            base_delay = 2.0
            for attempt in range(max_retries):
                try:
                    status_resp = poll_status(token, op_name, scene_id, interval_sec=base_delay, timeout_sec=300)
                    self.status_updated.emit(f"STT {stt}: ✅ Status: SUCCESSFUL với {account_name} - đang tải...")
                    break
                except RuntimeError as e:
                    if attempt == max_retries - 1:
                        self.status_updated.emit(f"STT {stt}: ❌ Status: FAILED với {account_name}!")
                        return (stt, prompt, False, f"Generation failed: {str(e)}")
                    else:
                        self.status_updated.emit(f"STT {stt}: ⚠️ Retry {attempt + 1}/{max_retries} với {account_name}...")
                        time.sleep(base_delay * (2 ** attempt))  # Exponential backoff
                except TimeoutError as e:
                    if attempt == max_retries - 1:
                        self.status_updated.emit(f"STT {stt}: ⏰ Timeout với {account_name}!")
                        return (stt, prompt, False, f"Timeout: {str(e)}")
                    else:
                        self.status_updated.emit(f"STT {stt}: ⚠️ Timeout, retry {attempt + 1}/{max_retries} với {account_name}...")
                        time.sleep(base_delay * (2 ** attempt))
                except Exception as e:
                    if attempt == max_retries - 1:
                        self.status_updated.emit(f"STT {stt}: ❌ Lỗi polling với {account_name}: {str(e)}")
                        return (stt, prompt, False, f"Polling error: {str(e)}")
                    else:
                        self.status_updated.emit(f"STT {stt}: ⚠️ Lỗi polling, retry {attempt + 1}/{max_retries} với {account_name}...")
                        time.sleep(base_delay * (2 ** attempt))
            
            # Download video
            self.status_updated.emit(f"STT {stt}: 📥 Downloading video từ {account_name}...")
            fife_url = extract_fife_url(status_resp)
            http_download_mp4(fife_url, output_path)
            
            self.status_updated.emit(f"STT {stt}: ✅ Hoàn thành với {account_name}: {output_filename}")
            return (stt, prompt, True, output_filename)
            
        except Exception as e:
            self.status_updated.emit(f"STT {stt}: ❌ Lỗi với {account_name}: {str(e)}")
            return (stt, prompt, False, str(e))
    
    def run(self):
        try:
            account_count = len(self.accounts_data)
            
            # Hiển thị thông tin chia tải
            distribution_info = []
            for account_name, data in self.account_prompts_distribution.items():
                distribution_info.append(f"{account_name}: {data['count']} prompts")
            
            distribution_text = " | ".join(distribution_info)
            self.progress_updated.emit(5, f"🚀 Bắt đầu xử lý {self.total_count} video với {self.max_workers} luồng và {account_count} tài khoản...")
            self.progress_updated.emit(8, f"📊 Chia tải: {distribution_text}")
            
            # Sử dụng ThreadPoolExecutor để xử lý parallel với chia tải tối ưu
            results = []
            self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
            
            try:
                # Tạo tasks với account distribution
                future_to_prompt = {}
                
                for account_name, data in self.account_prompts_distribution.items():
                    account_data = data['account']
                    prompts = data['prompts']
                    
                    # Submit tasks cho từng account
                    for prompt_data in prompts:
                        if self.should_stop:
                            break
                        future = self.executor.submit(self.process_video_with_specific_account, prompt_data, account_data)
                        future_to_prompt[future] = prompt_data
                
                # Xử lý kết quả khi hoàn thành với batch processing
                batch_size = max(1, self.total_count // 20)  # Update mỗi 5%
                batch_count = 0
                
                for future in as_completed(future_to_prompt):
                    if self.should_stop:
                        # Cancel các future còn lại
                        for f in future_to_prompt:
                            f.cancel()
                        break
                        
                    prompt_data = future_to_prompt[future]
                    stt, prompt, image_path = prompt_data
                    
                    try:
                        result = future.result()
                        results.append(result)
                        self.processed_count += 1
                        batch_count += 1
                        
                        # Tối ưu: Chỉ update progress mỗi batch để tránh lag UI
                        if batch_count >= batch_size or self.processed_count == self.total_count:
                            progress = int(10 + (self.processed_count / self.total_count) * 85)
                            status = "✓" if result[2] else "❌"
                            self.progress_updated.emit(
                                progress, 
                                f"{status} STT {stt}: {prompt[:30]}... ({self.processed_count}/{self.total_count})"
                            )
                            batch_count = 0
                        
                    except Exception as e:
                        results.append((stt, prompt, False, str(e)))
                        self.processed_count += 1
                        batch_count += 1
                        
            finally:
                # Shutdown executor
                if self.executor:
                    self.executor.shutdown(wait=False)
                        
            # Sắp xếp results theo STT
            results.sort(key=lambda x: x[0])
            
            # Thống kê kết quả
            successful = sum(1 for r in results if r[2])
            failed = len(results) - successful
            
            self.progress_updated.emit(100, f"✅ Hoàn thành! Thành công: {successful}/{len(results)} video")
            if failed > 0:
                self.progress_updated.emit(100, f"⚠️ Có {failed} video thất bại")
            
            self.finished.emit(results)
            
        except Exception as e:
            self.progress_updated.emit(0, f"❌ Lỗi: {str(e)}")
            self.finished.emit([])
        finally:
            # Tối ưu: Cleanup resources
            if hasattr(self, 'token_cache'):
                self.token_cache.clear()
            self.account_prompts_distribution.clear()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.accounts = []  # Danh sách tài khoản
        self.processing_thread = None  # Thread xử lý video
        self.is_processing = False  # Trạng thái đang xử lý
        self.init_ui()
        self.load_accounts()
        
    def init_ui(self):
        self.setWindowTitle("VEO 3 AI Video Generator - @huyit32")
        self.setGeometry(100, 100, 1200, 800)
        
        # Central widget với tab widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Tab 1: Quản lý tài khoản
        self.create_account_tab()
        
        # Tab 2: Xử lý video
        self.create_processing_tab()
        
        # Tab 3: Ghép video
        self.create_merge_tab()
        
    def create_account_tab(self):
        """Tab 1: Quản lý tài khoản"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Header
        header_layout = QHBoxLayout()
        add_btn = QPushButton("Add Cookie")
        add_btn.clicked.connect(self.add_cookie)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_accounts)
        
        header_layout.addWidget(add_btn)
        header_layout.addWidget(refresh_btn)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Table
        self.account_table = QTableWidget()
        self.account_table.setColumnCount(5)
        self.account_table.setHorizontalHeaderLabels(["NAME", "EMAIL", "STATUS", "EXPIRES", "ACTION"])
        self.account_table.horizontalHeader().setStretchLastSection(True)
        # Styling table
        self.account_table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border-radius: 3px;
                gridline-color: #e0e0e0;
                selection-background-color: #e3f2fd;
                alternate-background-color: #f8f9fa;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
                font-size: 8px;
            }
            QTableWidget::item:selected {
                background-color: transparent;
                color: inherit;
            }
            QTableWidget::item:hover {
                background-color: transparent;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                color: #333;
                padding: 8px;
                border: none;
                border-right: 1px solid #e0e0e0;
                border-bottom: 1px solid #e0e0e0;
                font-weight: bold;
                font-size: 10px;
                text-align: center;
            }
            QHeaderView::section:first {
                border-top-left-radius: 8px;
            }
            QHeaderView::section:last {
                border-top-right-radius: 8px;
                border-right: none;
            }
        """)

        
        # Table properties
        self.account_table.setAlternatingRowColors(True)
        self.account_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.account_table.setSelectionMode(QTableWidget.NoSelection)
        self.account_table.verticalHeader().setVisible(False)
        self.account_table.setShowGrid(True)
        self.account_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Set minimum row height for better appearance
        self.account_table.verticalHeader().setDefaultSectionSize(40)
        
        layout.addWidget(self.account_table)
        
        # Load accounts
        self.load_accounts_to_table()
        
        tab.setLayout(layout)
        self.tab_widget.addTab(tab, "Quản lý Tài khoản")
        
    def create_processing_tab(self):
        """Tab 2: Xử lý video"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Main layout với tỷ lệ cân đối
        main_layout = QHBoxLayout()
        
        # Left panel - Cấu hình (40%)
        left_panel = QWidget()
        left_panel.setMaximumWidth(500)
        left_layout = QVBoxLayout()
        
        # Group: Thông tin Tài khoản
        account_group = QGroupBox("Tài khoản (Tự động chia tải)")
        account_layout = QVBoxLayout()
        
        self.account_info_label = QLabel("Đang tải danh sách tài khoản...")
        self.account_info_label.setStyleSheet("""
            QLabel {
                color: #2196F3;
                font-size: 12px;
                font-weight: bold;
                padding: 8px;
                background-color: #e3f2fd;
                border-radius: 5px;
                border-left: 4px solid #2196F3;
            }
        """)
        account_layout.addWidget(self.account_info_label)
        
        # Auto refresh button
        refresh_accounts_btn = QPushButton("🔄 Làm mới danh sách")
        refresh_accounts_btn.clicked.connect(self.refresh_accounts)
        refresh_accounts_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        account_layout.addWidget(refresh_accounts_btn)
        
        # Test accounts button
        test_accounts_btn = QPushButton("🧪 Test Tài khoản")
        test_accounts_btn.clicked.connect(self.test_accounts_ui)
        test_accounts_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        account_layout.addWidget(test_accounts_btn)
        
        account_group.setLayout(account_layout)
        left_layout.addWidget(account_group)
        
        # Group: Cấu hình Video
        config_group = QGroupBox("Cấu hình Video")
        config_layout = QFormLayout()
        
        self.project_id_edit = QLineEdit("66a1a7a3-c9d9-4c42-a07e-44f2baecf60b")
        config_layout.addRow("Project ID:", self.project_id_edit)
        
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 65535)
        self.seed_spin.setValue(0)
        self.seed_spin.setSpecialValueText("Random")
        config_layout.addRow("Seed:", self.seed_spin)
        
        self.max_workers_spin = QSpinBox()
        self.max_workers_spin.setRange(1, 5)
        self.max_workers_spin.setValue(3)
        self.max_workers_spin.setToolTip("Số luồng xử lý song song (1-5)")
        config_layout.addRow("Threads:", self.max_workers_spin)
        
        # Aspect Ratio selection
        self.aspect_ratio_combo = QComboBox()
        self.aspect_ratio_combo.addItems([
            "16:9",
            "9:16"
        ])
        self.aspect_ratio_combo.setCurrentIndex(0)  # Default to landscape
        config_layout.addRow("Aspect Ratio:", self.aspect_ratio_combo)
        
        config_group.setLayout(config_layout)
        left_layout.addWidget(config_group)
        
        # Group: File Excel
        file_group = QGroupBox("File Excel")
        file_layout = QVBoxLayout()
        
        file_layout_h = QHBoxLayout()
        self.excel_path_edit = QLineEdit()
        self.excel_path_edit.setPlaceholderText("Chọn file Excel...")
        browse_btn = QPushButton("📁 Duyệt")
        browse_btn.clicked.connect(self.browse_excel)
        
        file_layout_h.addWidget(self.excel_path_edit)
        file_layout_h.addWidget(browse_btn)
        file_layout.addLayout(file_layout_h)
        
        self.require_image_check = QCheckBox("Yêu cầu có Image (cột C)")
        file_layout.addWidget(self.require_image_check)
        
        # Load Excel button
        load_excel_btn = QPushButton("📊 Load Excel")
        load_excel_btn.clicked.connect(self.load_excel_data)
        file_layout.addWidget(load_excel_btn)
        
        file_group.setLayout(file_layout)
        left_layout.addWidget(file_group)
        
        # Group: Excel Data Preview
        preview_group = QGroupBox("Excel Data Preview")
        preview_layout = QVBoxLayout()
        
        # Excel data table
        self.excel_table = QTableWidget()
        self.excel_table.setColumnCount(3)
        self.excel_table.setHorizontalHeaderLabels(["STT", "PROMPT", "IMAGE"])
        self.excel_table.horizontalHeader().setStretchLastSection(True)
        self.excel_table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border-radius: 3px;
                gridline-color: #e0e0e0;
                selection-background-color: #e3f2fd;
                alternate-background-color: #f8f9fa;
            }
            QTableWidget::item {
                padding: 6px;
                border-bottom: 1px solid #f0f0f0;
                font-size: 9px;
            }
            QTableWidget::item:selected {
                background-color: transparent;
                color: inherit;
            }
            QTableWidget::item:hover {
                background-color: transparent;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                color: #333;
                padding: 6px;
                border: none;
                border-right: 1px solid #e0e0e0;
                border-bottom: 1px solid #e0e0e0;
                font-weight: bold;
                font-size: 9px;
                text-align: center;
            }
        """)
        
        # Excel table properties
        self.excel_table.setAlternatingRowColors(True)
        self.excel_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.excel_table.setSelectionMode(QTableWidget.NoSelection)
        self.excel_table.verticalHeader().setVisible(False)
        self.excel_table.setShowGrid(True)
        self.excel_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.excel_table.setMaximumHeight(200)
        
        preview_layout.addWidget(self.excel_table)
        preview_group.setLayout(preview_layout)
        left_layout.addWidget(preview_group)
        
        # Group: Output
        output_group = QGroupBox("Output")
        output_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        output_layout = QHBoxLayout()
        
        self.output_dir_edit = QLineEdit("output")
        self.output_dir_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #e0e0e0;
                border-radius: 5px;
                background-color: white;
                font-size: 12px;
                color: #333;
            }
        """)
        
        self.browse_output_btn = QPushButton("📁 Chọn Folder")
        self.browse_output_btn.clicked.connect(self.browse_output_dir)
        self.browse_output_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        output_layout.addWidget(self.output_dir_edit)
        output_layout.addWidget(self.browse_output_btn)
        output_group.setLayout(output_layout)
        left_layout.addWidget(output_group)
        
        left_layout.addStretch()
        left_panel.setLayout(left_layout)
        
        # Right panel - Progress và Log (60%)
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        # Progress section
        progress_group = QGroupBox("Tiến độ Xử lý")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #e0e0e0;
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
                background-color: #f5f5f5;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        
        self.progress_label = QLabel("Sẵn sàng")
        self.progress_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #666;
                padding: 5px;
                background-color: #f8f9fa;
                border-radius: 3px;
                border-left: 3px solid #2196F3;
            }
        """)
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        progress_group.setLayout(progress_layout)
        right_layout.addWidget(progress_group)
        
        # Log section
        log_group = QGroupBox("Log Xử lý")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #333;
                border-radius: 5px;
                font-family: "Consolas", "Monaco", monospace;
                font-size: 11px;
                padding: 10px;
            }
        """)
        
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        right_layout.addWidget(log_group)
        
        # Control buttons
        control_group = QGroupBox("Điều khiển")
        control_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("🚀 Bắt đầu Xử lý")
        self.start_btn.clicked.connect(self.start_processing)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        
        self.stop_btn = QPushButton("⏹️ Dừng")
        self.stop_btn.clicked.connect(self.stop_processing)
        self.stop_btn.setEnabled(False)  # Disabled by default
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addStretch()
        control_group.setLayout(control_layout)
        right_layout.addWidget(control_group)
        
        right_panel.setLayout(right_layout)
        
        # Add panels to main layout
        main_layout.addWidget(left_panel, 2)  # 40%
        main_layout.addWidget(right_panel, 3)  # 60%
        
        layout.addLayout(main_layout)
        tab.setLayout(layout)
        self.tab_widget.addTab(tab, "Xử lý Video")
        
    def create_merge_tab(self):
        """Tab 3: Ghép video"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Main layout với tỷ lệ cân đối
        main_layout = QHBoxLayout()
        
        # Left panel - Video list và controls (60%)
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        
        # Group: Video List
        video_group = QGroupBox("Danh sách Video")
        video_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        video_layout = QVBoxLayout()
        
        # Header buttons
        header_layout = QHBoxLayout()
        add_video_btn = QPushButton("📁 Thêm Video")
        add_video_btn.clicked.connect(self.add_video_to_merge)
        add_video_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        clear_btn = QPushButton("🗑️ Xóa tất cả")
        clear_btn.clicked.connect(self.clear_merge_list)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        
        header_layout.addWidget(add_video_btn)
        header_layout.addWidget(clear_btn)
        header_layout.addStretch()
        
        video_layout.addLayout(header_layout)
        
        # Video table với styling giống tab 1
        self.video_table = QTableWidget()
        self.video_table.setColumnCount(3)
        self.video_table.setHorizontalHeaderLabels(["STT", "FILE VIDEO", "ĐƯỜNG DẪN"])
        
        # Styling video table giống tab 1
        self.video_table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border-radius: 3px;
                gridline-color: #e0e0e0;
                selection-background-color: #e3f2fd;
                alternate-background-color: #f8f9fa;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
                font-size: 7px;
            }
            QTableWidget::item:selected {
                background-color: transparent;
                color: inherit;
            }
            QTableWidget::item:hover {
                background-color: transparent;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                color: #333;
                padding: 8px;
                border: none;
                border-right: 1px solid #e0e0e0;
                border-bottom: 1px solid #e0e0e0;
                font-weight: bold;
                font-size: 10px;
                text-align: center;
            }
            QHeaderView::section:first {
                border-top-left-radius: 8px;
            }
            QHeaderView::section:last {
                border-top-right-radius: 8px;
                border-right: none;
            }
        """)
        
        # Video table properties
        self.video_table.horizontalHeader().setStretchLastSection(True)
        self.video_table.setAlternatingRowColors(True)
        self.video_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.video_table.setSelectionMode(QTableWidget.NoSelection)
        self.video_table.verticalHeader().setVisible(False)
        self.video_table.setShowGrid(True)
        self.video_table.setSortingEnabled(False)  # Không sort để giữ thứ tự
        self.video_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Set column widths
        self.video_table.verticalHeader().setDefaultSectionSize(40)
        video_layout.addWidget(self.video_table, 1)  # Stretch factor = 1 để table mở rộng
        video_group.setLayout(video_layout)
        left_layout.addWidget(video_group, 1)  # Stretch factor = 1 để group mở rộng
        
        # Group: Tùy chọn Ghép
        options_group = QGroupBox("Tùy chọn Ghép")
        options_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        options_layout = QFormLayout()
        
        self.output_name_edit = QLineEdit("merged_video.mp4")
        self.output_name_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #e0e0e0;
                border-radius: 5px;
                background-color: white;
                font-size: 12px;
                color: #333;
            }
        """)
        options_layout.addRow("Tên file output:", self.output_name_edit)
        
        # Transition removed - always no transitions for clean merging
        
        # Audio toggle - improved labeling
        self.mute_audio_check = QCheckBox("Tắt âm thanh (chỉ giữ video)")
        self.mute_audio_check.setStyleSheet("""
            QCheckBox {
                font-size: 12px;
                color: #333;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:checked {
                background-color: #FF9800;
                border: 2px solid #FF9800;
                border-radius: 3px;
            }
            QCheckBox::indicator:unchecked {
                background-color: white;
                border: 2px solid #e0e0e0;
                border-radius: 3px;
            }
        """)
        options_layout.addRow("Âm thanh:", self.mute_audio_check)
        
        options_group.setLayout(options_layout)
        left_layout.addWidget(options_group)
        
        # Merge button
        self.merge_btn = QPushButton("🔗 Ghép Video")
        self.merge_btn.clicked.connect(self.merge_videos)
        self.merge_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
        """)
        
        left_layout.addWidget(self.merge_btn)
        left_layout.addStretch()
        
        left_panel.setLayout(left_layout)
        main_layout.addWidget(left_panel)
        
        # Right panel - Progress và Log (40%)
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        # Group: Tiến độ Ghép
        progress_group = QGroupBox("Tiến độ Ghép")
        progress_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        progress_layout = QVBoxLayout()
        
        self.merge_progress_bar = QProgressBar()
        self.merge_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #e0e0e0;
                border-radius: 5px;
                text-align: center;
                background-color: white;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #FF9800;
                border-radius: 3px;
            }
        """)
        progress_layout.addWidget(self.merge_progress_bar)
        
        self.merge_progress_label = QLabel("Sẵn sàng ghép video")
        self.merge_progress_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 12px;
            }
        """)
        progress_layout.addWidget(self.merge_progress_label)
        
        progress_group.setLayout(progress_layout)
        right_layout.addWidget(progress_group)
        
        # Group: Log Ghép
        log_group = QGroupBox("Log Ghép Video")
        log_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        log_layout = QVBoxLayout()
        
        self.merge_log_text = QTextEdit()
        self.merge_log_text.setReadOnly(True)
        self.merge_log_text.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 5px;
                font-family: "Consolas", "Monaco", monospace;
                font-size: 11px;
                padding: 8px;
            }
        """)
        log_layout.addWidget(self.merge_log_text)
        
        log_group.setLayout(log_layout)
        right_layout.addWidget(log_group)
        
        right_panel.setLayout(right_layout)
        main_layout.addWidget(right_panel)
        
        tab.setLayout(main_layout)
        self.tab_widget.addTab(tab, "Ghép Video")
        
    def add_cookie(self):
        """Thêm cookie mới"""
        dialog = AddCookieDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"] and data["cookie"]:
                self.accounts.append(data)
                self.save_accounts()
                self.load_accounts_to_table()
                self.update_account_info()
                
                msg = create_styled_messagebox(self, "Thành công", "✅ Đã thêm cookie thành công!")
                msg.exec_()
            else:
                create_styled_messagebox(self, "Lỗi", "Vui lòng nhập đầy đủ thông tin!", QMessageBox.Warning).exec_()
                
    def load_accounts(self):
        """Load accounts từ file"""
        try:
            if os.path.exists("accounts.json"):
                with open("accounts.json", "r", encoding="utf-8") as f:
                    self.accounts = json.load(f)
            else:
                self.accounts = []
        except Exception as e:
            print(f"Lỗi load accounts: {e}")
            self.accounts = []
        
        # Cập nhật thông tin tài khoản
        self.update_account_info()
            
    def save_accounts(self):
        """Save accounts ra file"""
        try:
            with open("accounts.json", "w", encoding="utf-8") as f:
                json.dump(self.accounts, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Lỗi save accounts: {e}")
            
    def load_accounts_to_table(self):
        """Load accounts vào table"""
        self.account_table.setRowCount(len(self.accounts))
        
        for i, account in enumerate(self.accounts):
            # Tên tài khoản
            name_item = QTableWidgetItem(account.get("name", ""))
            name_item.setFont(QFont("Roboto", 9, QFont.Bold))
            name_item.setTextAlignment(Qt.AlignCenter)
            self.account_table.setItem(i, 0, name_item)
            
            # Extract email from cookie if possible
            email = "Unknown"
            try:
                cookie_text = account.get("cookie", "")
                if "email" in cookie_text.lower():
                    import urllib.parse
                    
                    # Multiple patterns to catch different email formats
                    patterns = [
                        r'email["\']?\s*[:=]\s*["\']?([^"\';\s]+)',  # email: value
                        r'["\']?email["\']?\s*[:=]\s*["\']?([^"\';\s]+)',  # "email": value
                        r'%40([^%]+)%40',  # URL encoded @ symbol
                        r'@([^;\s]+)',  # Direct @ pattern
                    ]
                    
                    for pattern in patterns:
                        email_match = re.search(pattern, cookie_text, re.IGNORECASE)
                        if email_match:
                            raw_email = email_match.group(1)
                            # Decode URL-encoded email
                            email = urllib.parse.unquote(raw_email)
                            
                            # Validate email format
                            if '@' in email and '.' in email.split('@')[-1]:
                                break
                            else:
                                email = "Unknown"
            except:
                pass
                
            email_item = QTableWidgetItem(email)
            email_item.setFont(QFont("Roboto", 10))
            email_item.setTextAlignment(Qt.AlignCenter)
            if email != "Unknown":
                email_item.setForeground(Qt.darkBlue)
            self.account_table.setItem(i, 1, email_item)
            
            # Trạng thái đơn giản
            status = account.get("status", "Unknown")
            if "Done" in status:
                status_display = "Done"
                status_color = Qt.darkGreen
            elif "Error" in status:
                status_display = "Error"
                status_color = Qt.darkRed
            else:
                status_display = "Unknown"
                status_color = Qt.darkGray
                
            status_item = QTableWidgetItem(status_display)
            status_item.setFont(QFont("Roboto", 10))
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setForeground(status_color)
            self.account_table.setItem(i, 2, status_item)
            
            # Thời gian expires
            expires_text = account.get("expires", "Unknown")
            expires_item = QTableWidgetItem(expires_text)
            expires_item.setFont(QFont("Roboto", 10))
            expires_item.setTextAlignment(Qt.AlignCenter)
            
            # Kiểm tra cookie có hết hạn không để đổi màu
            if expires_text != "Unknown":
                try:
                    from datetime import datetime, timezone, timedelta
                    # Parse thời gian từ format "dd/mm/yyyy hh:mm:ss"
                    expires_time = datetime.strptime(expires_text, "%d/%m/%Y %H:%M:%S")
                    # Chuyển sang timezone Việt Nam (UTC+7)
                    expires_time = expires_time.replace(tzinfo=timezone(timedelta(hours=7)))
                    current_time = datetime.now(timezone(timedelta(hours=7)))
                    
                    if expires_time <= current_time:
                        # Cookie đã hết hạn - màu đỏ
                        expires_item.setForeground(Qt.red)
                        expires_item.setFont(QFont("Roboto", 10, QFont.Bold))
                    else:
                        # Cookie còn hiệu lực - màu xanh
                        expires_item.setForeground(Qt.darkGreen)
                except:
                    # Nếu không parse được thì để màu mặc định
                    expires_item.setForeground(Qt.darkGray)
            else:
                expires_item.setForeground(Qt.darkGray)
                
            self.account_table.setItem(i, 3, expires_item)
            
            # Container cho các nút action
            action_widget = QWidget()
            action_layout = QHBoxLayout()
            action_layout.setContentsMargins(2, 2, 2, 2)
            action_layout.setSpacing(4)
            
            # Nút Checker
            checker_btn = QPushButton("🔍 Checker")
            checker_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border: none;
                    padding: 4px 8px;
                    border-radius: 3px;
                    font-weight: bold;
                    font-size: 9px;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
                QPushButton:pressed {
                    background-color: #1565C0;
                }
            """)
            checker_btn.clicked.connect(lambda checked, row=i: self.check_cookie_expiry(row))
            
            # Nút xóa
            delete_btn = QPushButton("🗑️ Xóa")
            delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    padding: 4px 8px;
                    border-radius: 3px;
                    font-weight: bold;
                    font-size: 9px;
                }
                QPushButton:hover {
                    background-color: #d32f2f;
                }
                QPushButton:pressed {
                    background-color: #b71c1c;
                }
            """)
            delete_btn.clicked.connect(lambda checked, row=i: self.delete_account(row))
            
            action_layout.addWidget(checker_btn)
            action_layout.addWidget(delete_btn)
            action_widget.setLayout(action_layout)
            self.account_table.setCellWidget(i, 4, action_widget)
            
        # Auto resize columns và set column widths
        self.account_table.resizeColumnsToContents()
        
        # Set column widths properly
        header = self.account_table.horizontalHeader()
        header.setSectionResizeMode(0, header.Stretch)  # NAME
        header.setSectionResizeMode(1, header.Stretch)  # EMAIL  
        header.setSectionResizeMode(2, header.ResizeToContents)  # STATUS
        header.setSectionResizeMode(3, header.ResizeToContents)  # EXPIRES
        header.setSectionResizeMode(4, header.ResizeToContents)  # ACTION
            
    def delete_account(self, row):
        """Xóa tài khoản tại row được chỉ định"""
        if row < 0 or row >= len(self.accounts):
            return
            
        # Lấy thông tin tài khoản để hiển thị trong dialog
        account = self.accounts[row]
        account_name = account.get("name", "Unknown")
        account_email = "Unknown"
        
        # Extract email from cookie if possible
        try:
            cookie_text = account.get("cookie", "")
            if "email" in cookie_text.lower():
                import urllib.parse
                patterns = [
                    r'email["\']?\s*[:=]\s*["\']?([^"\';\s]+)',
                    r'["\']?email["\']?\s*[:=]\s*["\']?([^"\';\s]+)',
                    r'%40([^%]+)%40',
                    r'@([^;\s]+)',
                ]
                
                for pattern in patterns:
                    email_match = re.search(pattern, cookie_text, re.IGNORECASE)
                    if email_match:
                        raw_email = email_match.group(1)
                        email = urllib.parse.unquote(raw_email)
                        if '@' in email and '.' in email.split('@')[-1]:
                            account_email = email
                            break
        except:
            pass
        
        # Hiển thị dialog xác nhận
        msg = QMessageBox()
        msg.setWindowTitle("Xác nhận xóa tài khoản")
        msg.setText(f"Bạn có chắc chắn muốn xóa tài khoản này?")
        msg.setInformativeText(f"Tên: {account_name}\nEmail: {account_email}")
        msg.setIcon(QMessageBox.Warning)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        
        # Styling cho message box
        msg.setStyleSheet("""
            QMessageBox {
                background-color: white;
                font-family: "Segoe UI";
                font-size: 12px;
            }
            QMessageBox QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        
        if msg.exec_() == QMessageBox.Yes:
            # Xóa tài khoản khỏi danh sách
            del self.accounts[row]
            
            # Lưu lại file accounts.json
            self.save_accounts()
            
            # Refresh table
            self.load_accounts_to_table()
            self.update_account_info()
            
            # Hiển thị thông báo thành công
            create_styled_messagebox(self, "Thành công", f"Đã xóa tài khoản {account_name}").exec_()

    def check_cookie_expiry(self, row):
        """Kiểm tra cookie hết hạn cho tài khoản tại row được chỉ định"""
        if row >= len(self.accounts):
            return
            
        account = self.accounts[row]
        account_name = account.get("name", "Unknown")
        cookie_text = account.get("cookie", "")
        
        if not cookie_text or cookie_text.startswith("YOUR_COOKIE_HERE"):
            create_styled_messagebox(self, "Lỗi", f"Cookie không hợp lệ cho tài khoản {account_name}").exec_()
            return
        
        try:
            # Test cookie bằng cách gọi session API
            headers = {
                "Accept": "application/json",
                "Cookie": cookie_text,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get("https://labs.google/fx/api/auth/session", 
                                  headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                user_info = data.get("user", {})
                user_name = user_info.get("name", "Unknown")
                user_email = user_info.get("email", "Unknown")
                
                # Lấy thời gian expires
                expires_str = data.get("expires", "")
                if expires_str:
                    try:
                        # Parse thời gian UTC
                        from datetime import datetime, timezone, timedelta
                        utc_time = datetime.fromisoformat(expires_str.replace('Z', '+00:00'))
                        # Chuyển sang giờ Việt Nam (UTC+7)
                        vn_time = utc_time.astimezone(timezone(timedelta(hours=7)))
                        current_time = datetime.now(timezone(timedelta(hours=7)))
                        
                        # Kiểm tra cookie có hết hạn không
                        if vn_time <= current_time:
                            # Cookie đã hết hạn
                            expires_display = vn_time.strftime("%d/%m/%Y %H:%M:%S")
                            message = f"⚠️ Cookie đã hết hạn!\n\nTài khoản: {account_name}\nEmail: {user_email}\nHết hạn: {expires_display}\n\nVui lòng truy cập web để lấy cookie mới."
                            create_styled_messagebox(self, "Cookie Hết Hạn", message, QMessageBox.Critical).exec_()
                        else:
                            # Cookie còn hiệu lực
                            expires_display = vn_time.strftime("%d/%m/%Y %H:%M:%S")
                            time_left = vn_time - current_time
                            days_left = time_left.days
                            hours_left = time_left.seconds // 3600
                            
                            if days_left > 0:
                                time_info = f"{days_left} ngày {hours_left} giờ"
                            else:
                                time_info = f"{hours_left} giờ"
                            
                            message = f"✅ Cookie còn hiệu lực!\n\nTài khoản: {account_name}\nEmail: {user_email}\nHết hạn: {expires_display}\nCòn lại: {time_info}"
                            create_styled_messagebox(self, "Cookie Hợp Lệ", message).exec_()
                    except Exception as e:
                        message = f"Cookie hợp lệ nhưng không thể parse thời gian hết hạn.\n\nTài khoản: {account_name}\nEmail: {user_email}\nExpires: {expires_str}"
                        create_styled_messagebox(self, "Cookie Hợp Lệ", message).exec_()
                else:
                    message = f"Cookie hợp lệ nhưng không có thông tin thời gian hết hạn.\n\nTài khoản: {account_name}\nEmail: {user_email}"
                    create_styled_messagebox(self, "Cookie Hợp Lệ", message).exec_()
            else:
                # Cookie không hợp lệ hoặc hết hạn
                message = f"❌ Cookie không hợp lệ hoặc đã hết hạn!\n\nTài khoản: {account_name}\nStatus Code: {response.status_code}\n\nVui lòng truy cập web để lấy cookie mới."
                create_styled_messagebox(self, "Cookie Không Hợp Lệ", message, QMessageBox.Critical).exec_()
                
        except requests.exceptions.Timeout:
            message = f"⏳ Timeout khi kiểm tra cookie!\n\nTài khoản: {account_name}\n\nVui lòng kiểm tra kết nối mạng và thử lại."
            create_styled_messagebox(self, "Timeout", message).exec_()
        except requests.exceptions.ConnectionError:
            message = f"📡 Không thể kết nối!\n\nTài khoản: {account_name}\n\nVui lòng kiểm tra kết nối mạng và thử lại."
            create_styled_messagebox(self, "Lỗi Kết Nối", message).exec_()
        except Exception as e:
            message = f"❌ Lỗi khi kiểm tra cookie!\n\nTài khoản: {account_name}\nLỗi: {str(e)}\n\nVui lòng truy cập web để lấy cookie mới."
            create_styled_messagebox(self, "Lỗi", message, QMessageBox.Critical).exec_()

    def refresh_accounts(self):
        """Làm mới danh sách accounts"""
        self.load_accounts()
        self.load_accounts_to_table()
        self.update_account_info()
        
    def update_account_info(self):
        """Cập nhật thông tin tài khoản cho auto distribution"""
        # Kiểm tra xem account_info_label đã được khởi tạo chưa
        if not hasattr(self, 'account_info_label'):
            return
            
        if not self.accounts:
            self.account_info_label.setText("❌ Không có tài khoản nào!")
            self.account_info_label.setStyleSheet("""
                QLabel {
                    color: #f44336;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 8px;
                    background-color: #ffebee;
                    border-radius: 5px;
                    border-left: 4px solid #f44336;
                }
            """)
            return
        
        # Đếm số tài khoản active
        active_accounts = [acc for acc in self.accounts if "Done" in acc.get("status", "")]
        total_accounts = len(self.accounts)
        active_count = len(active_accounts)
        
        if active_count == 0:
            self.account_info_label.setText("⚠️ Không có tài khoản nào hoạt động!")
            self.account_info_label.setStyleSheet("""
                QLabel {
                    color: #ff9800;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 8px;
                    background-color: #fff3e0;
                    border-radius: 5px;
                    border-left: 4px solid #ff9800;
                }
            """)
        else:
            self.account_info_label.setText(f"✅ {active_count}/{total_accounts} tài khoản hoạt động\n🔄 Tự động chia tải giữa các tài khoản")
            self.account_info_label.setStyleSheet("""
                QLabel {
                    color: #4caf50;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 8px;
                    background-color: #e8f5e8;
                    border-radius: 5px;
                    border-left: 4px solid #4caf50;
                }
            """)
                
    def browse_excel(self):
        """Chọn file Excel"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file Excel", "", "Excel files (*.xlsx *.xls)"
        )
        if file_path:
            self.excel_path_edit.setText(file_path)
            
    def browse_output_dir(self):
        """Chọn thư mục output"""
        current_dir = self.output_dir_edit.text().strip()
        if not current_dir or not os.path.exists(current_dir):
            current_dir = os.getcwd()  # Default to current directory
            
        dir_path = QFileDialog.getExistingDirectory(
            self, 
            "Chọn thư mục lưu video", 
            current_dir
        )
        if dir_path:
            self.output_dir_edit.setText(dir_path)
            self.log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📁 Đã chọn folder output: {dir_path}")
            
    def load_excel_data(self):
        """Load và hiển thị dữ liệu Excel"""
        excel_path = self.excel_path_edit.text()
        if not excel_path:
            create_styled_messagebox(self, "Lỗi", "Vui lòng chọn file Excel trước!", QMessageBox.Warning).exec_()
            return
            
        if not os.path.exists(excel_path):
            create_styled_messagebox(self, "Lỗi", "File Excel không tồn tại!", QMessageBox.Warning).exec_()
            return
            
        try:
            require_image = self.require_image_check.isChecked()
            prompts = read_excel_prompts(excel_path, require_image)
            
            if not prompts:
                create_styled_messagebox(self, "Lỗi", "Không có dữ liệu nào trong file Excel!", QMessageBox.Warning).exec_()
                return
                
            # Hiển thị dữ liệu trong table
            self.excel_table.setRowCount(len(prompts))
            
            for i, (stt, prompt, image_path) in enumerate(prompts):
                # STT
                stt_item = QTableWidgetItem(str(stt))
                stt_item.setFont(QFont("Roboto", 9))
                stt_item.setTextAlignment(Qt.AlignCenter)
                stt_item.setForeground(Qt.darkBlue)
                self.excel_table.setItem(i, 0, stt_item)
                
                # PROMPT
                prompt_item = QTableWidgetItem(prompt)
                prompt_item.setFont(QFont("Roboto", 9))
                prompt_item.setTextAlignment(Qt.AlignLeft)
                self.excel_table.setItem(i, 1, prompt_item)
                
                # IMAGE - Lưu đường dẫn đầy đủ thay vì chỉ tên file
                image_display = "None"
                if image_path:
                    if os.path.exists(image_path):
                        image_display = image_path  # Lưu đường dẫn đầy đủ
                    else:
                        image_display = "❌ Not found"
                        
                image_item = QTableWidgetItem(image_display)
                image_item.setFont(QFont("Roboto", 9))
                image_item.setTextAlignment(Qt.AlignCenter)
                
                if image_display == "None":
                    image_item.setForeground(Qt.darkGray)
                elif image_display == "❌ Not found":
                    image_item.setForeground(Qt.darkRed)
                else:
                    image_item.setForeground(Qt.darkGreen)
                    
                self.excel_table.setItem(i, 2, image_item)
                
            # Auto resize columns
            self.excel_table.resizeColumnsToContents()
            
            # Set column widths
            header = self.excel_table.horizontalHeader()
            header.setSectionResizeMode(0, header.ResizeToContents)  # STT
            header.setSectionResizeMode(1, header.Stretch)  # PROMPT
            header.setSectionResizeMode(2, header.ResizeToContents)  # IMAGE
            
            create_styled_messagebox(self, "Thành công", f"✅ Đã load {len(prompts)} dòng dữ liệu từ Excel!").exec_()
            
        except Exception as e:
            create_styled_messagebox(self, "Lỗi", f"Lỗi đọc file Excel: {str(e)}", QMessageBox.Critical).exec_()
            
    def test_accounts(self):
        """Test tất cả tài khoản trước khi chạy"""
        valid_accounts = []
        
        for account in self.accounts:
            cookie = account.get("cookie", "")
            name = account.get("name", "Unknown")
            
            if not cookie or cookie.startswith("YOUR_COOKIE_HERE"):
                self.log_text.append(f"⚠️ {name}: Cookie không hợp lệ")
                continue
                
            token = fetch_access_token_from_session(cookie)
            if token:
                valid_accounts.append(account)
                self.log_text.append(f"✅ {name}: Token hợp lệ")
            else:
                self.log_text.append(f"❌ {name}: Không thể lấy token - Cookie có thể đã hết hạn")
        
        return valid_accounts

    def test_accounts_ui(self):
        """Test tài khoản với UI feedback"""
        if not self.accounts:
            create_styled_messagebox(self, "Lỗi", "Không có tài khoản nào để test!", QMessageBox.Warning).exec_()
            return
        
        self.log_text.append("🔍 Đang kiểm tra tài khoản...")
        valid_accounts = self.test_accounts()
        
        if valid_accounts:
            create_styled_messagebox(self, "Kết quả Test", f"✅ {len(valid_accounts)}/{len(self.accounts)} tài khoản hợp lệ!\n\nCó thể bắt đầu xử lý video.", QMessageBox.Information).exec_()
        else:
            create_styled_messagebox(self, "Kết quả Test", "❌ Không có tài khoản nào hợp lệ!\n\nVui lòng:\n1. Kiểm tra lại cookie\n2. Thêm tài khoản mới\n3. Đảm bảo cookie chưa hết hạn", QMessageBox.Warning).exec_()

    def start_processing(self):
        """Bắt đầu xử lý video với auto account distribution"""
        # Validate inputs
        if not self.accounts:
            create_styled_messagebox(self, "Lỗi", "Không có tài khoản nào! Vui lòng thêm tài khoản trước.", QMessageBox.Warning).exec_()
            return
        
        # Test tài khoản trước khi chạy
        self.log_text.append("🔍 Đang kiểm tra tài khoản...")
        valid_accounts = self.test_accounts()
        
        if not valid_accounts:
            create_styled_messagebox(self, "Lỗi", "Không có tài khoản nào hợp lệ! Vui lòng kiểm tra lại cookie.", QMessageBox.Warning).exec_()
            return
        
        self.log_text.append(f"✅ Tìm thấy {len(valid_accounts)} tài khoản hợp lệ")
            
        if not self.excel_path_edit.text():
            create_styled_messagebox(self, "Lỗi", "Vui lòng chọn file Excel!", QMessageBox.Warning).exec_()
            return
            
        if not os.path.exists(self.excel_path_edit.text()):
            create_styled_messagebox(self, "Lỗi", "File Excel không tồn tại!", QMessageBox.Warning).exec_()
            return
            
        # Check if Excel data is loaded
        if self.excel_table.rowCount() == 0:
            create_styled_messagebox(self, "Lỗi", "Vui lòng load dữ liệu Excel trước!", QMessageBox.Warning).exec_()
            return
            
        # Get prompts from loaded Excel data
        prompts = []
        for row in range(self.excel_table.rowCount()):
            stt_item = self.excel_table.item(row, 0)
            prompt_item = self.excel_table.item(row, 1)
            image_item = self.excel_table.item(row, 2)
            
            if stt_item and prompt_item:
                stt = int(stt_item.text())
                prompt = prompt_item.text()
                image_path = None
                
                # Get image path if exists
                if image_item and image_item.text() not in ["None", "❌ Not found"]:
                    # Use full path directly from table (already stored as full path)
                    image_path = image_item.text()
                    print(f"DEBUG: STT {stt} - Image path: {image_path}")
                    print(f"DEBUG: STT {stt} - Image exists: {os.path.exists(image_path)}")
                else:
                    print(f"DEBUG: STT {stt} - No image or image not found")
                    
                prompts.append((stt, prompt, image_path))
                
        if not prompts:
            create_styled_messagebox(self, "Lỗi", "Không có prompt nào để xử lý!", QMessageBox.Warning).exec_()
            return
            
        # Prepare config
        output_dir = self.output_dir_edit.text().strip()
        if not output_dir:
            output_dir = "output"  # Default folder
            
        # Get aspect ratio from combo box
        aspect_ratio_text = self.aspect_ratio_combo.currentText()
        if aspect_ratio_text == "9:16":
            aspect_ratio = "VIDEO_ASPECT_RATIO_PORTRAIT"
        else:  # "16:9" or default
            aspect_ratio = "VIDEO_ASPECT_RATIO_LANDSCAPE"
            
        config = {
            "project_id": self.project_id_edit.text(),
            "seed": self.seed_spin.value(),
            "max_workers": self.max_workers_spin.value(),
            "output_dir": output_dir,
            "aspect_ratio": aspect_ratio
        }
        
        # Create output directory
        os.makedirs(config["output_dir"], exist_ok=True)
        
        # Disable start button và enable stop button
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.is_processing = True
        self.progress_bar.setValue(0)
        self.log_text.clear()
        
        # Start processing thread với auto account distribution (chỉ sử dụng tài khoản hợp lệ)
        max_workers = self.max_workers_spin.value()
        self.processing_thread = VideoProcessingThread(prompts, valid_accounts, config, max_workers)
        self.processing_thread.progress_updated.connect(self.on_progress_updated)
        self.processing_thread.status_updated.connect(self.on_status_updated)
        self.processing_thread.finished.connect(self.on_processing_finished)
        self.processing_thread.start()
        
    def on_progress_updated(self, progress, message):
        """Update progress"""
        self.progress_bar.setValue(progress)
        self.progress_label.setText(message)
        self.log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        self.log_text.ensureCursorVisible()  # Auto scroll to bottom
        
    def on_status_updated(self, status_message):
        """Update status log"""
        self.log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] {status_message}")
        self.log_text.ensureCursorVisible()  # Auto scroll to bottom
        
    def on_processing_finished(self, results):
        """Khi xử lý hoàn thành"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.is_processing = False
        
        # Hiển thị dialog kết quả chuyên nghiệp
        dialog = ProcessingResultDialog(results, self)
        dialog.exec_()
        
        # Show detailed results in log
        self.log_text.append(f"\n=== KẾT QUẢ CHI TIẾT ===")
        for stt, prompt, success, result in results:
            if success:
                self.log_text.append(f"✓ STT {stt}: {result}")
            else:
                self.log_text.append(f"❌ STT {stt}: {result}")
    
    def stop_processing(self):
        """Dừng quá trình xử lý video"""
        if not self.is_processing or not self.processing_thread:
            return
        
        # Xác nhận với người dùng
        msg = QMessageBox(self)
        msg.setWindowTitle("Xác nhận dừng")
        msg.setText("Bạn có chắc chắn muốn dừng quá trình xử lý video?")
        msg.setInformativeText("Các video đang xử lý sẽ bị hủy và không thể khôi phục.")
        msg.setIcon(QMessageBox.Warning)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        
        if msg.exec_() == QMessageBox.Yes:
            # Dừng thread bằng cách set flag should_stop
            if self.processing_thread and hasattr(self.processing_thread, 'stop_processing'):
                self.processing_thread.stop_processing()
            
            # Đợi một chút để thread có thể dừng gracefully
            self.processing_thread.wait(3000)  # Đợi tối đa 3 giây
            
            # Force terminate nếu vẫn chưa dừng
            if self.processing_thread.isRunning():
                self.processing_thread.terminate()
                self.processing_thread.wait()
            
            # Reset UI
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.is_processing = False
            
            # Hiển thị thông báo
            self.log_text.append(f"\n⏹️ ĐÃ DỪNG QUÁ TRÌNH XỬ LÝ VIDEO")
            self.progress_label.setText("Đã dừng xử lý video")
            create_styled_messagebox(self, "Thông báo", "Đã dừng quá trình xử lý video!", QMessageBox.Information).exec_()
    
    def retry_failed_videos(self, failed_videos):
        """Chạy lại các video thất bại"""
        if not failed_videos:
            return
        
        # Lấy thông tin từ failed videos
        retry_prompts = []
        for stt, prompt, success, error in failed_videos:
            # Tìm image path từ Excel table
            image_path = None
            for row in range(self.excel_table.rowCount()):
                stt_item = self.excel_table.item(row, 0)
                if stt_item and int(stt_item.text()) == stt:
                    image_item = self.excel_table.item(row, 2)
                    if image_item and image_item.text() not in ["None", "❌ Not found"]:
                        image_path = image_item.text()
                    break
            
            retry_prompts.append((stt, prompt, image_path))
        
        # Lấy tài khoản hợp lệ
        valid_accounts = []
        for account in self.accounts:
            cookie_text = account.get("cookie", "")
            if cookie_text and not cookie_text.startswith("YOUR_COOKIE_HERE"):
                valid_accounts.append(account)
        
        if not valid_accounts:
            create_styled_messagebox(self, "Lỗi", "Không có tài khoản hợp lệ để chạy lại!", QMessageBox.Warning).exec_()
            return
        
        # Chuẩn bị config (sử dụng cùng config như lần trước)
        output_dir = self.output_dir_edit.text().strip()
        if not output_dir:
            output_dir = "output"
        
        aspect_ratio_text = self.aspect_ratio_combo.currentText()
        if aspect_ratio_text == "9:16":
            aspect_ratio = "VIDEO_ASPECT_RATIO_PORTRAIT"
        else:
            aspect_ratio = "VIDEO_ASPECT_RATIO_LANDSCAPE"
        
        config = {
            "project_id": self.project_id_edit.text(),
            "output_dir": output_dir,
            "aspect_ratio": aspect_ratio,
            "proxy": None
        }
        
        # Disable start button, enable stop button và reset progress
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.is_processing = True
        self.progress_bar.setValue(0)
        self.log_text.append(f"\n🔄 BẮT ĐẦU CHẠY LẠI {len(retry_prompts)} VIDEO THẤT BẠI...")
        
        # Start processing thread với retry prompts
        max_workers = self.max_workers_spin.value()
        self.processing_thread = VideoProcessingThread(retry_prompts, valid_accounts, config, max_workers)
        self.processing_thread.progress_updated.connect(self.on_progress_updated)
        self.processing_thread.status_updated.connect(self.on_status_updated)
        self.processing_thread.finished.connect(self.on_processing_finished)
        self.processing_thread.start()
                
    def add_video_to_merge(self):
        """Thêm video vào danh sách ghép"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Chọn video để ghép", "", "Video files (*.mp4 *.avi *.mov *.mkv)"
        )
        
        for file_path in file_paths:
            row = self.video_table.rowCount()
            self.video_table.insertRow(row)
            
            # Thứ tự
            order_item = QTableWidgetItem(str(row + 1))
            order_item.setFont(QFont("Roboto", 8, QFont.Bold))
            order_item.setForeground(Qt.darkBlue)
            order_item.setTextAlignment(Qt.AlignCenter)
            self.video_table.setItem(row, 0, order_item)
            
            # Tên file
            filename_item = QTableWidgetItem(os.path.basename(file_path))
            filename_item.setFont(QFont("Roboto", 8))
            filename_item.setForeground(Qt.darkGreen)
            filename_item.setTextAlignment(Qt.AlignCenter)
            self.video_table.setItem(row, 1, filename_item)
            
            # Đường dẫn
            path_item = QTableWidgetItem(file_path)
            path_item.setFont(QFont("Roboto", 8))
            path_item.setForeground(Qt.darkGray)
            path_item.setTextAlignment(Qt.AlignCenter)
            self.video_table.setItem(row, 2, path_item)
            
        # Auto resize columns
        self.video_table.resizeColumnsToContents()
            
    def clear_merge_list(self):
        """Xóa tất cả video trong danh sách"""
        self.video_table.setRowCount(0)
        
    def merge_videos(self):
        """Ghép các video lại với nhau"""
        if self.video_table.rowCount() < 2:
            create_styled_messagebox(self, "Lỗi", "Cần ít nhất 2 video để ghép!", QMessageBox.Warning).exec_()
            return
            
        # Collect video paths
        video_paths = []
        for row in range(self.video_table.rowCount()):
            path_item = self.video_table.item(row, 2)
            if path_item:
                video_paths.append(path_item.text())
                
        if len(video_paths) < 2:
            create_styled_messagebox(self, "Lỗi", "Không đủ video hợp lệ!", QMessageBox.Warning).exec_()
            return
            
        # Output path
        output_name = self.output_name_edit.text()
        if not output_name.endswith('.mp4'):
            output_name += '.mp4'
            
        output_path = os.path.join(os.path.dirname(video_paths[0]), output_name)
        
        # Get audio setting
        mute_audio = self.mute_audio_check.isChecked()
        
        # Disable merge button và clear log
        self.merge_btn.setEnabled(False)
        self.merge_progress_bar.setValue(0)
        self.merge_log_text.clear()
        
        # Start merge thread
        self.merge_thread = VideoMergeThread(video_paths, output_path, mute_audio)
        self.merge_thread.progress_updated.connect(self.on_merge_progress_updated)
        self.merge_thread.log_updated.connect(self.on_merge_log_updated)
        self.merge_thread.finished.connect(self.on_merge_finished)
        self.merge_thread.start()
        
    def on_merge_progress_updated(self, progress, message):
        """Update merge progress"""
        self.merge_progress_bar.setValue(progress)
        self.merge_progress_label.setText(message)
        
    def on_merge_log_updated(self, message):
        """Update merge log"""
        self.merge_log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        self.merge_log_text.ensureCursorVisible()
        
    def on_merge_finished(self, success, message):
        """Khi ghép video hoàn thành"""
        # Re-enable merge button
        self.merge_btn.setEnabled(True)
        
        if success:
            create_styled_messagebox(self, "Thành công", message).exec_()
        else:
            create_styled_messagebox(self, "Lỗi", message, QMessageBox.Critical).exec_()



    
from auth.auth_guard import KeyLoginDialog, get_device_id
from version_checker import check_for_update, CURRENT_VERSION
import sys
import logging

# Constants
API_URL = "http://62.171.131.164:5000"
API_AUTH_ENDPOINT = f"{API_URL}/api/make_video_ai/auth"
VERSION_CHECK_ENDPOINT = f"{API_URL}/api/version.json"
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main application entry point"""
    try:
        app = QApplication(sys.argv)
        app.setStyleSheet("""
        QMainWindow {
            background-color: #f0f0f0;
        }
        QTabWidget::pane {
            border: 1px solid #c0c0c0;
            background-color: white;
        }
        QTabBar::tab {
            background-color: #e0e0e0;
            padding: 8px 16px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background-color: white;
            border-bottom: 2px solid #2196F3;
        }
        QTableWidget {
            gridline-color: #e0e0e0;
            background-color: white;
            alternate-background-color: #f8f9fa;
            border: 1px solid #d0d0d0;
            border-radius: 8px;
            font-family: "Roboto", "Open Sans", "Segoe UI";
        }
        QTableWidget::item {
            padding: 12px 8px;
            border-bottom: 1px solid #f0f0f0;
            font-size: 8px;
            font-family: "Roboto", "Open Sans", "Segoe UI";
        }
        QTableWidget::item:selected {
            background-color: #e3f2fd;
            color: #1976d2;
        }
        QTableWidget::item:hover {
            background-color: #f5f5f5;
        }
        QHeaderView::section {
            background-color: #f8f9fa;
            color: #333;
            padding: 12px 8px;
            border: none;
            border-right: 1px solid #e0e0e0;
            border-bottom: 2px solid #2196F3;
            font-weight: bold;
            font-size: 14px;
            font-family: "Roboto", "Open Sans", "Segoe UI";
        }
        QGroupBox {
            font-weight: bold;
            font-size: 12px;
            border: 1px solid #d0d0d0;
            border-radius: 8px;
            margin-top: 10px;
            padding-top: 15px;
            background-color: #fafafa;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 15px;
            padding: 0 8px 0 8px;
            color: #333;
            background-color: #fafafa;
        }
    """)
        # Check for updates
        if check_for_update(VERSION_CHECK_ENDPOINT):
            logger.info("Update check completed, exiting")
            return 0
            
        # Authenticate user
        login_dialog = KeyLoginDialog(API_AUTH_ENDPOINT)
        if login_dialog.exec_() != QDialog.Accepted or not login_dialog.validated:
            logger.warning("Authentication failed or cancelled")
            return 0
            
        # Get authentication info
        key_info = login_dialog.key_info
        key = key_info.get("key")
        expires_raw = key_info.get("expires", "")
        remaining = key_info.get("remaining", 0)
        device_id = get_device_id()[0]
        
        logger.info(f"Authentication successful - Key: {key}, Device: {device_id}, Remaining: {remaining}")
        
        # Create and show main UI
        ui = MainWindow()
        expires = expires_raw if expires_raw else "Unknown"
        window_title = f"Veo3 AI Generator v{CURRENT_VERSION} - @huyit32 - KEY: {key} | Expires: {expires} | Remaining: {remaining}"
        ui.setWindowTitle(window_title)
        ui.show()
        
        return app.exec_()
        
    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())