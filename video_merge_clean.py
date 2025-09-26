# Phương pháp ghép video thay thế FFmpeg

import os
import sys
import subprocess
import platform

# Import các thư viện ghép video thay thế
try:
    from moviepy.editor import VideoFileClip, concatenate_videoclips
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

def merge_videos_moviepy(video_paths, output_path):
    """Ghép video sử dụng MoviePy"""
    if not MOVIEPY_AVAILABLE:
        print("⚠️ MoviePy không có sẵn!")
        return False
    
    try:
        print("🎬 Sử dụng MoviePy để ghép video...")
        
        # Load các video clips
        clips = []
        for i, video_path in enumerate(video_paths):
            print(f"📹 Đang load video {i+1}/{len(video_paths)}...")
            clip = VideoFileClip(video_path)
            clips.append(clip)
        
        # Ghép video
        print("🔗 Đang ghép video...")
        final_clip = concatenate_videoclips(clips)
        
        # Xuất video
        print("💾 Đang xuất video...")
        final_clip.write_videofile(output_path, 
                                 codec='libx264', 
                                 audio_codec='aac',
                                 temp_audiofile='temp-audio.m4a',
                                 remove_temp=True)
        
        # Cleanup
        final_clip.close()
        for clip in clips:
            clip.close()
        
        print("✅ Ghép video thành công với MoviePy!")
        return True
        
    except Exception as e:
        print(f"❌ Lỗi MoviePy: {str(e)}")
        return False

def merge_videos_opencv(video_paths, output_path):
    """Ghép video sử dụng OpenCV"""
    if not OPENCV_AVAILABLE:
        print("⚠️ OpenCV không có sẵn!")
        return False
    
    try:
        print("🎥 Sử dụng OpenCV để ghép video...")
        
        # Lấy thông tin video đầu tiên
        cap = cv2.VideoCapture(video_paths[0])
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        
        # Tạo video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        # Ghép từng video
        for i, video_path in enumerate(video_paths):
            print(f"📹 Đang xử lý video {i+1}/{len(video_paths)}...")
            
            cap = cv2.VideoCapture(video_path)
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                out.write(frame)
            cap.release()
        
        out.release()
        print("✅ Ghép video thành công với OpenCV!")
        return True
        
    except Exception as e:
        print(f"❌ Lỗi OpenCV: {str(e)}")
        return False

def merge_videos_ffmpeg(video_paths, output_path):
    """Ghép video sử dụng FFmpeg"""
    try:
        print("🎞️ Sử dụng FFmpeg để ghép video...")
        
        # Tạo file list
        import tempfile
        concat_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        for video_path in video_paths:
            escaped_path = video_path.replace("'", "'\"'\"'").replace("\\", "\\\\")
            concat_file.write(f"file '{escaped_path}'\n")
        concat_file.close()
        
        # Ghép video với FFmpeg
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file.name,
               "-c:v", "libx264", "-c:a", "aac", "-preset", "fast", "-crf", "23",
               output_path]
        
        # Ẩn cửa sổ CMD trên Windows
        startupinfo = None
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
        
        result = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo)
        
        # Cleanup
        try:
            os.unlink(concat_file.name)
        except:
            pass
        
        if result.returncode == 0:
            print("✅ Ghép video thành công với FFmpeg!")
            return True
        else:
            print(f"❌ Lỗi FFmpeg: {result.stderr[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ Lỗi FFmpeg: {str(e)}")
        return False

def merge_videos(video_paths, output_path):
    """Ghép video sử dụng phương pháp tốt nhất có sẵn"""
    print(f"🚀 Bắt đầu ghép {len(video_paths)} video...")
    
    # Kiểm tra file tồn tại
    for i, video_path in enumerate(video_paths):
        if not os.path.exists(video_path):
            print(f"❌ Video {i+1} không tồn tại: {video_path}")
            return False
    
    print("✅ Tất cả video files hợp lệ")
    
    # Thử các phương pháp theo thứ tự ưu tiên
    methods = [
        ("MoviePy", merge_videos_moviepy),
        ("OpenCV", merge_videos_opencv),
        ("FFmpeg", merge_videos_ffmpeg)
    ]
    
    for method_name, method_func in methods:
        print(f"\n🔄 Thử phương pháp {method_name}...")
        if method_func(video_paths, output_path):
            print(f"✅ Thành công với {method_name}!")
            return True
        else:
            print(f"❌ Thất bại với {method_name}")
    
    print("❌ Tất cả phương pháp đều thất bại!")
    return False

if __name__ == "__main__":
    # Test với video paths
    video_paths = [
        "video1.mp4",
        "video2.mp4",
        "video3.mp4"
    ]
    output_path = "merged_video.mp4"
    
    success = merge_videos(video_paths, output_path)
    if success:
        print(f"🎉 Video đã được ghép thành công: {output_path}")
    else:
        print("😞 Không thể ghép video!")