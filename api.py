import os
import json
import time
import threading
import re
import uuid
import random
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import pandas as pd


API_URL = "http://62.171.131.164:5000"
GENERATE_URL = "https://aisandbox-pa.googleapis.com/v1/video:batchAsyncGenerateVideoText"
GENERATE_IMAGE_URL = "https://aisandbox-pa.googleapis.com/v1/video:batchAsyncGenerateVideoStartImage"
UPSCALE_URL = "https://aisandbox-pa.googleapis.com/v1/video:batchAsyncGenerateVideoUpsampleVideo"
CHECK_URL = "https://aisandbox-pa.googleapis.com/v1/video:batchCheckAsyncVideoGenerationStatus"
SESSION_URL = "https://labs.google/fx/api/auth/session"
UPLOAD_IMAGE_URL = "https://aisandbox-pa.googleapis.com/v1:uploadUserImage"

# User-Agent giả lập trình duyệt thật
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36"
]

# Headers giả lập trình duyệt thật
BROWSER_HEADERS = {
	"Accept": "application/json, text/plain, */*",
	"Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
	"Accept-Encoding": "gzip, deflate, br",
	"Cache-Control": "no-cache",
	"Pragma": "no-cache",
	"Connection": "keep-alive"
}


# Các hàm FFmpeg đã được loại bỏ vì không còn cần thiết
# Giờ đây tải trực tiếp file MP4 từ URL


def get_random_user_agent() -> str:
	"""Lấy User-Agent ngẫu nhiên"""
	return random.choice(USER_AGENTS)


def get_browser_headers() -> Dict[str, str]:
	"""Tạo headers giả lập trình duyệt thật"""
	headers = BROWSER_HEADERS.copy()
	headers["User-Agent"] = get_random_user_agent()
	return headers


def get_api_headers(token: str) -> Dict[str, str]:
	"""Tạo headers cho API requests với token"""
	header_token = token.strip()
	if header_token.lower().startswith("bearer "):
		header_token = header_token.split(" ", 1)[1]
	
	# Headers cơ bản cho API - loại bỏ Origin để tránh xung đột
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {header_token}",
		"User-Agent": get_random_user_agent(),
		"Accept": "application/json",
		"Accept-Language": "en-US,en;q=0.9",
		"Accept-Encoding": "gzip, deflate, br"
	}
	
	return headers


def get_session_config() -> Dict[str, Any]:
	"""Tạo cấu hình session giả lập"""
	return {
		"verify": True,
		"allow_redirects": True,
		"timeout": (60, 300)  # (connect timeout, read timeout) - tăng timeout lên 5 phút cho video generation
	}


def add_random_delay(min_delay: float = 0.1, max_delay: float = 0.5) -> None:
	"""Thêm delay ngẫu nhiên để giả lập hành vi người dùng thật"""
	time.sleep(random.uniform(min_delay, max_delay))


def auto_retry_with_backoff(func, *args, max_retries: int = 3, base_delay: float = 1.0, 
                           max_delay: float = 60.0, backoff_factor: float = 2.0, 
                           retry_on_exceptions: tuple = (Exception,), **kwargs):
	"""
	Tự động retry một hàm với exponential backoff
	
	Args:
		func: Hàm cần retry
		*args: Arguments cho hàm
		max_retries: Số lần retry tối đa
		base_delay: Delay cơ bản (giây)
		max_delay: Delay tối đa (giây)
		backoff_factor: Hệ số tăng delay
		retry_on_exceptions: Tuple các exception cần retry
		**kwargs: Keyword arguments cho hàm
	
	Returns:
		Kết quả của hàm nếu thành công
		
	Raises:
		Exception cuối cùng nếu hết số lần retry
	"""
	last_exception = None
	
	for attempt in range(max_retries + 1):  # +1 vì attempt đầu tiên không phải retry
		try:
			return func(*args, **kwargs)
		except retry_on_exceptions as e:
			last_exception = e
			
			if attempt < max_retries:
				# Tính delay với exponential backoff
				delay = min(base_delay * (backoff_factor ** attempt), max_delay)
				# Thêm jitter để tránh thundering herd
				jitter = random.uniform(0.1, 0.3) * delay
				final_delay = delay + jitter
				
				print(f"🔄 Lỗi lần {attempt + 1}/{max_retries + 1}: {str(e)[:100]}...")
				print(f"⏳ Thử lại sau {final_delay:.1f} giây...")
				time.sleep(final_delay)
			else:
				print(f"❌ Đã thử {max_retries + 1} lần nhưng vẫn lỗi: {str(e)}")
				break
	
	# Nếu đến đây thì đã hết số lần retry
	raise last_exception


def http_post_json(url: str, payload: Dict[str, Any], token: str, proxy: Optional[Dict[str, str]] = None, max_retries: int = 5) -> Dict[str, Any]:
	headers = get_api_headers(token)
	session_config = get_session_config()
	
	# Tạo session với cấu hình giả lập
	session = requests.Session()
	session.headers.update(headers)
	
	for attempt in range(max_retries):
		try:
			# Thêm delay ngẫu nhiên để giả lập hành vi người dùng thật
			if attempt > 0:
				# Delay lâu hơn khi retry
				add_random_delay(1.0, 3.0)
			else:
				add_random_delay(0.1, 0.5)
			
			# Thử với proxy trước, nếu lỗi thì thử không proxy
			current_proxy = proxy
			if attempt > 0 and proxy:
				print(f"🔄 Lần thử {attempt + 1}: Thử không proxy...")
				current_proxy = None
			
			resp = session.post(
				url, 
				data=json.dumps(payload), 
				proxies=current_proxy,
				**session_config
			)
			resp.raise_for_status()
			return resp.json()
			
		except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError) as e:
			print(f"❌ Lỗi proxy/connection (lần thử {attempt + 1}/{max_retries}): {e}")
			if attempt < max_retries - 1:
				print(f"🔄 Thử lại sau {2 ** attempt} giây...")
				time.sleep(2 ** attempt)
				continue
			else:
				raise
				
		except requests.exceptions.Timeout as e:
			print(f"⏰ Timeout (lần thử {attempt + 1}/{max_retries}): {e}")
			if attempt < max_retries - 1:
				print(f"🔄 Thử lại sau {3 ** attempt} giây...")
				time.sleep(3 ** attempt)  # Delay lâu hơn cho timeout
				continue
			else:
				raise
				
		except requests.HTTPError as e:
			# Debug: In ra response chi tiết khi có lỗi
			print(f"❌ Lỗi HTTP {e.response.status_code} (lần thử {attempt + 1}/{max_retries}): {e.response.text}")
			
			# Nếu là lỗi 500 và chưa hết số lần thử, thử lại
			if e.response.status_code == 500 and attempt < max_retries - 1:
				print(f"🔄 Thử lại sau {2 ** attempt} giây...")
				time.sleep(2 ** attempt)  # Exponential backoff
				continue
			
			# Nếu là lỗi khác hoặc đã hết số lần thử, raise exception
			if attempt == max_retries - 1:
				print(f"API Request failed after {max_retries} attempts")
				print(f"Request Headers: {dict(session.headers)}")
			raise



def http_download_mp4(url: str, output_path: str, proxy: Optional[Dict[str, str]] = None) -> None:
	"""Tải trực tiếp file mp4 từ URL"""
	headers = get_browser_headers()
	session = requests.Session()
	session.headers.update(headers)
	
	with session.get(url, stream=True, timeout=120, proxies=proxy) as r:
		r.raise_for_status()
		with open(output_path, "wb") as f:
			for chunk in r.iter_content(chunk_size=1024 * 1024):
				if chunk:
					f.write(chunk)


def get_encoded_video(token: str, media_id: str, proxy: Optional[Dict[str, str]] = None) -> Optional[str]:
	"""Lấy encodedVideo từ mediaId sau khi upscale"""
	print(f"🚀 DEBUG: get_encoded_video được gọi!")
	print(f"🚀 DEBUG: media_id: {media_id}")
	
	url = f"https://aisandbox-pa.googleapis.com/v1/media/{media_id}?clientContext.tool=PINHOLE"
	headers = get_api_headers(token)
	
	session = requests.Session()
	session.headers.update(headers)
	session_config = get_session_config()
	
	try:
		resp = session.get(url, proxies=proxy, **session_config)
		resp.raise_for_status()
		data = resp.json()
		
		# Trích xuất encodedVideo
		video_data = data.get("video", {})
		encoded_video = video_data.get("encodedVideo")
		
		if encoded_video:
			print(f"✅ Đã lấy encodedVideo từ mediaId: {media_id[:20]}...")
			return encoded_video
		else:
			print(f"❌ Không tìm thấy encodedVideo trong response")
			return None
			
	except Exception as e:
		print(f"❌ Lỗi lấy encodedVideo: {e}")
		return None


def download_encoded_video(encoded_video: str, output_path: str) -> None:
	"""Tải video từ encodedVideo string"""
	print(f"🚀 DEBUG: download_encoded_video được gọi!")
	print(f"🚀 DEBUG: output_path: {output_path}")
	print(f"🚀 DEBUG: encoded_video length: {len(encoded_video)}")
	
	try:
		import base64
		# Decode base64 encoded video
		video_data = base64.b64decode(encoded_video)
		
		# Ghi file video
		with open(output_path, 'wb') as f:
			f.write(video_data)
		
		print(f"✅ Đã tải video từ encodedVideo: {output_path}")
		
	except Exception as e:
		print(f"❌ Lỗi tải video từ encodedVideo: {e}")
		raise


def delete_media(names: List[str], cookie_header_value: Optional[str], proxy: Optional[Dict[str, str]] = None, max_retries: int = 3) -> bool:
	"""Gọi API xóa media trên labs.google. Trả về True nếu thành công.

	API: https://labs.google/fx/api/trpc/media.deleteMedia (POST)
	Body: {"json": {"names": ["<media_id>", ...]}}
	"""
	if not cookie_header_value:
		print("⚠ Bỏ qua xóa media do thiếu Cookie")
		return False
	
	url = "https://labs.google/fx/api/trpc/media.deleteMedia"
	headers = get_browser_headers()
	headers.update({
		"Accept": "application/json",
		"Content-Type": "application/json",
		"Cookie": cookie_header_value,
	})
	
	session = requests.Session()
	session.headers.update(headers)
	session_config = get_session_config()
	payload = {"json": {"names": names}}
	
	for attempt in range(max_retries):
		try:
			if attempt > 0:
				add_random_delay(0.5, 1.5)
			resp = session.post(url, data=json.dumps(payload), proxies=proxy, **session_config)
			resp.raise_for_status()
			print("🧹 Đã gửi yêu cầu xóa media thành công")
			return True
		except requests.HTTPError as e:
			print(f"❌ Xóa media lỗi HTTP {e.response.status_code}: {e.response.text}")
			if e.response.status_code >= 500 and attempt < max_retries - 1:
				print("🔄 Thử xóa lại...")
				continue
			return False
		except Exception as e:
			print(f"❌ Xóa media lỗi: {e}")
			return False


def upload_image(token: str, image_path: str, proxy: Optional[Dict[str, str]] = None) -> str:
	"""Upload image và trả về mediaGenerationId"""
	if not os.path.exists(image_path):
		raise FileNotFoundError(f"Không tìm thấy file image: {image_path}")
	
	# Đọc file image
	with open(image_path, "rb") as f:
		image_data = f.read()
	
	# Chuyển đổi thành base64
	import base64
	base64_data = base64.b64encode(image_data).decode('utf-8')
	
	# Xác định mime type
	mime_type = "image/jpeg"
	if image_path.lower().endswith('.png'):
		mime_type = "image/png"
	elif image_path.lower().endswith('.gif'):
		mime_type = "image/gif"
	elif image_path.lower().endswith('.webp'):
		mime_type = "image/webp"
	
	# Tạo session ID ngẫu nhiên
	session_id = f";{int(time.time() * 1000)}"
	
	payload = {
		"imageInput": {
			"aspectRatio": "IMAGE_ASPECT_RATIO_LANDSCAPE",
			"isUserUploaded": True,
			"mimeType": mime_type,
			"rawImageBytes": base64_data
		},
		"clientContext": {
			"sessionId": session_id,
			"tool": "ASSET_MANAGER"
		}
	}
	
	response = http_post_json(UPLOAD_IMAGE_URL, payload, token, proxy)
	
	# Trích xuất mediaGenerationId
	media_gen_id = response.get("mediaGenerationId", {}).get("mediaGenerationId")
	if not media_gen_id:
		raise ValueError("Không tìm thấy mediaGenerationId trong phản hồi upload")
	
	return media_gen_id


def upload_video(token: str, video_path: str, proxy: Optional[Dict[str, str]] = None) -> str:
	"""Upload video và trả về mediaGenerationId - sử dụng cùng endpoint nhưng với payload video"""
	print(f"🚀 DEBUG: upload_video được gọi!")
	print(f"🚀 DEBUG: video_path: {video_path}")
	print(f"🚀 DEBUG: video_path exists: {os.path.exists(video_path)}")
	
	if not os.path.exists(video_path):
		raise FileNotFoundError(f"Không tìm thấy file video: {video_path}")
	
	# Đọc file video
	with open(video_path, "rb") as f:
		video_data = f.read()
	
	# Chuyển đổi thành base64
	import base64
	base64_data = base64.b64encode(video_data).decode('utf-8')
	
	# Xác định mime type
	mime_type = "video/mp4"
	if video_path.lower().endswith('.mov'):
		mime_type = "video/quicktime"
	elif video_path.lower().endswith('.avi'):
		mime_type = "video/x-msvideo"
	elif video_path.lower().endswith('.webm'):
		mime_type = "video/webm"
	
	# Tạo session ID ngẫu nhiên
	session_id = f";{int(time.time() * 1000)}"
	
	# Sử dụng cùng endpoint nhưng với payload video (sử dụng imageInput thay vì videoInput)
	payload = {
		"imageInput": {
			"aspectRatio": "VIDEO_ASPECT_RATIO_LANDSCAPE",
			"isUserUploaded": True,
			"mimeType": mime_type,
			"rawImageBytes": base64_data
		},
		"clientContext": {
			"sessionId": session_id,
			"tool": "ASSET_MANAGER"
		}
	}
	
	response = http_post_json(UPLOAD_IMAGE_URL, payload, token, proxy)
	
	# Trích xuất mediaGenerationId
	media_gen_id = response.get("mediaGenerationId", {}).get("mediaGenerationId")
	if not media_gen_id:
		raise ValueError("Không tìm thấy mediaGenerationId trong phản hồi upload video")
	
	return media_gen_id


def generate_video(token: str, prompt: str, project_id: str, model_key: str = "veo_3_0_t2v_fast_ultra", aspect_ratio: str = "VIDEO_ASPECT_RATIO_LANDSCAPE", seed: Optional[int] = None, proxy: Optional[Dict[str, str]] = None) -> Tuple[Dict[str, Any], str]:
	"""Generate video và trả về response cùng với scene_id được tạo"""
	if seed is None:
		# Đọc seed từ config, nếu seed = 0 thì random
		config = _load_config()
		config_seed = config.get("seed", 0)
		if config_seed == 0:
			seed = int(time.time()) % 65535
		else:
			seed = config_seed
	
	# Tạo scene_id ngẫu nhiên
	scene_id = str(uuid.uuid4())
	
	payload = {
		"clientContext": {
			"projectId": project_id,
			"tool": "PINHOLE",
			"userPaygateTier": "PAYGATE_TIER_TWO",
		},
		"requests": [
			{
				"aspectRatio": aspect_ratio,
				"seed": seed,
				"textInput": {"prompt": prompt},
				"videoModelKey": model_key,
				"metadata": {"sceneId": scene_id},
			}
		]
	}
	response = http_post_json(GENERATE_URL, payload, token, proxy)
	return response, scene_id


def generate_video_from_image(token: str, prompt: str, media_id: str, project_id: str, model_key: str = "veo_3_i2v_s_fast_ultra", aspect_ratio: str = "VIDEO_ASPECT_RATIO_LANDSCAPE", seed: Optional[int] = None, proxy: Optional[Dict[str, str]] = None) -> Tuple[Dict[str, Any], str]:
	"""Generate video từ image + prompt và trả về response cùng với scene_id được tạo"""
	if seed is None:
		# Đọc seed từ config, nếu seed = 0 thì random
		config = _load_config()
		config_seed = config.get("seed", 0)
		if config_seed == 0:
			seed = int(time.time()) % 65535
		else:
			seed = config_seed
	
	# Tạo scene_id ngẫu nhiên
	scene_id = str(uuid.uuid4())
	
	payload = {
		"clientContext": {
			"projectId": project_id,
			"tool": "PINHOLE",
			"userPaygateTier": "PAYGATE_TIER_TWO"
		},
		"requests": [
			{
				"aspectRatio": aspect_ratio,
				"seed": seed,
				"textInput": {
					"prompt": prompt
				},
				"promptExpansionInput": {
					"prompt": prompt,
					"seed": seed,
					"templateId": "0TNlfC6bSF",
					"imageInputs": [
						{
							"mediaId": media_id,
							"imageUsageType": "IMAGE_USAGE_TYPE_UNSPECIFIED"
						}
					]
				},
				"videoModelKey": model_key,
				"startImage": {
					"mediaId": media_id
				},
				"metadata": {
					"sceneId": scene_id
				}
			}
		]
	}
	response = http_post_json(GENERATE_IMAGE_URL, payload, token, proxy)
	return response, scene_id


def upscale_video(token: str, video_media_id: str, project_id: str, scale: str = "1080p", aspect_ratio: str = "VIDEO_ASPECT_RATIO_LANDSCAPE", seed: Optional[int] = None, proxy: Optional[Dict[str, str]] = None) -> Tuple[Dict[str, Any], str]:
	"""Upscale video và trả về response cùng với scene_id được tạo"""
	if seed is None:
		# Đọc seed từ config, nếu seed = 0 thì random
		config = _load_config()
		config_seed = config.get("seed", 0)
		if config_seed == 0:
			seed = int(time.time()) % 65535
		else:
			seed = config_seed
	
	# Tạo scene_id ngẫu nhiên
	scene_id = str(uuid.uuid4())
	
	# Chọn model key dựa trên scale
	if scale == "720p":
		model_key = "veo_2_720p_upsampler_8s"
	elif scale == "1080p":
		model_key = "veo_2_1080p_upsampler_8s"
	else:
		model_key = "veo_2_1080p_upsampler_8s"  # Default to 1080p
	
	# Tạo session ID ngẫu nhiên
	session_id = f";{int(time.time() * 1000)}"
	
	payload = {
		"clientContext": {
			"sessionId": session_id
		},
		"requests": [
			{
				"aspectRatio": aspect_ratio,
				"seed": seed,
				"videoInput": {
					"mediaId": video_media_id
				},
				"videoModelKey": model_key,
				"metadata": {
					"sceneId": scene_id
				}
			}
		]
	}
	response = http_post_json(UPSCALE_URL, payload, token, proxy)
	return response, scene_id


def extract_op_name(response_json: Dict[str, Any]) -> str:
	ops = response_json.get("operations", [])
	if not ops:
		raise ValueError("Không có operations trong phản hồi generate")
	operation = ops[0].get("operation", {})
	name = operation.get("name")
	if not name:
		raise ValueError("Không có operation.name trong phản hồi generate")
	return name


def poll_status(token: str, operation_name: str, scene_id: str, interval_sec: float = 3.0, timeout_sec: int = 1200, proxy: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
	deadline = time.time() + timeout_sec
	last_status = None
	while time.time() < deadline:
		payload = {
			"operations": [
				{
					"operation": {"name": operation_name},
					"sceneId": scene_id,
				}
			]
		}
		resp = http_post_json(CHECK_URL, payload, token, proxy)
		ops = resp.get("operations", [])
		if not ops:
			raise ValueError("Phản hồi status không có operations")
		status = ops[0].get("status")
		if status != last_status:
			print(f"Status: {status}")
			last_status = status
		if status == "MEDIA_GENERATION_STATUS_SUCCESSFUL":
			return resp
		if status in {"MEDIA_GENERATION_STATUS_FAILED", "MEDIA_GENERATION_STATUS_CANCELLED"}:
			raise RuntimeError(f"Media generation thất bại: {json.dumps(resp, ensure_ascii=False)}")
		time.sleep(interval_sec)
	raise TimeoutError("Hết thời gian chờ media generation")


def _extract_media_id_from_operation(operation: Dict[str, Any], search_paths: List[List[str]], debug_prefix: str) -> Optional[str]:
	"""Hàm chung để trích xuất mediaId từ operation với các đường dẫn tìm kiếm"""
	media_id = None
	
	for i, path in enumerate(search_paths):
		current = operation
		path_str = ".".join(path)
		
		try:
			for key in path:
				if isinstance(current, dict) and key in current:
					current = current[key]
				else:
					current = None
					break
			
			if current:
				media_id = current
				print(f"✅ {debug_prefix} - Found mediaId at: {path_str}")
				break
		except Exception as e:
			continue
	
	return media_id


def extract_video_media_id(status_json: Dict[str, Any]) -> Optional[str]:
	"""Trích xuất mediaId từ video generation response"""
	try:
		operations = status_json.get("operations", [])
		
		if operations:
			operation = operations[0]
			
			# Đường dẫn tìm kiếm cho video generation
			search_paths = [
				["mediaGenerationId"],  # Vị trí 1: operation.mediaGenerationId
				["response", "mediaId"],  # Vị trí 2: operation.response.mediaId
				["operation", "mediaId"],  # Vị trí 3: operation.operation.mediaId
				["metadata", "mediaId"]   # Vị trí 4: operation.metadata.mediaId
			]
			
			media_id = _extract_media_id_from_operation(operation, search_paths, "Video mediaId")
			
			if media_id:
				return media_id
		
		print("❌ Không tìm thấy mediaId trong video generation response")
		return None
	except Exception as e:
		print(f"❌ Lỗi trích xuất video mediaId: {e}")
		return None


def extract_upscale_media_id(response_json: Dict[str, Any]) -> Optional[str]:
	"""Trích xuất mediaId từ response upscale"""
	try:
		operations = response_json.get("operations", [])
		
		if operations:
			operation = operations[0]
			
			# Đường dẫn tìm kiếm cho upscale response
			search_paths = [
				["mediaGenerationId"],  # Vị trí 1: operation.mediaGenerationId
				["metadata", "video", "mediaGenerationId"],  # Vị trí 2: operation.metadata.video.mediaGenerationId
				["response", "mediaId"]  # Vị trí 3: operation.response.mediaId (backup)
			]
			
			media_id = _extract_media_id_from_operation(operation, search_paths, "Upscale mediaId")
			
			if media_id:
				return media_id
		
		print("❌ Không tìm thấy mediaId trong upscale response")
		return None
	except Exception as e:
		print(f"❌ Lỗi trích xuất upscale mediaId: {e}")
		return None


def extract_fife_url(status_json: Dict[str, Any]) -> str:
	ops = status_json.get("operations", [])
	if not ops:
		raise ValueError("Không có operations trong phản hồi status")
	operation = ops[0].get("operation", {})
	metadata = operation.get("metadata", {})
	video = metadata.get("video", {})
	url = video.get("fifeUrl") or video.get("fife_url")
	if not url:
		raise ValueError("Không tìm thấy fifeUrl trong phản hồi status")
	return url



def _load_config() -> Dict[str, Any]:
	"""Đọc cấu hình từ file config.json"""
	try:
		with open("config.json", "r", encoding="utf-8") as f:
			return json.load(f)
	except FileNotFoundError:
		print("⚠ File config.json không tồn tại, sử dụng giá trị mặc định")
		return {}
	except json.JSONDecodeError as e:
		print(f"⚠ Lỗi đọc file config.json: {e}, sử dụng giá trị mặc định")
		return {}
	except Exception as e:
		print(f"⚠ Lỗi không xác định khi đọc config.json: {e}, sử dụng giá trị mặc định")
		return {}


def fetch_access_token_from_session(cookie_header_value: str, proxy: Optional[Dict[str, str]] = None) -> Optional[str]:
	# Gọi GET tới SESSION_URL kèm Cookie để lấy access_token
	headers = get_browser_headers()
	headers.update({
		"Accept": "application/json",
		"Cookie": cookie_header_value,
	})
	
	# Thêm delay ngẫu nhiên để giả lập hành vi người dùng thật
	add_random_delay(0.2, 0.8)
	
	session = requests.Session()
	session.headers.update(headers)
	session_config = get_session_config()
	
	resp = session.get(SESSION_URL, proxies=proxy, **session_config)
	resp.raise_for_status()
	try:
		data = resp.json()
	except ValueError:
		return None
	
	# Hiển thị thông tin user và thời gian hết hạn
	user_info = data.get("user", {})
	user_name = user_info.get("name", "Unknown")
	user_email = user_info.get("email", "Unknown")
	expires = data.get("expires", "Unknown")
	
	# Chuyển đổi thời gian hết hạn sang giờ Việt Nam
	expires_vn = "Unknown"
	if expires != "Unknown":
		try:
			# Parse thời gian UTC
			utc_time = datetime.fromisoformat(expires.replace('Z', '+00:00'))
			# Chuyển sang giờ Việt Nam (UTC+7)
			vn_time = utc_time.astimezone(timezone(timedelta(hours=7)))
			# Format theo định dạng Việt Nam
			expires_vn = vn_time.strftime("%d/%m/%Y %H:%M:%S (UTC+7)")
		except (ValueError, TypeError):
			expires_vn = expires
	
	print(f"Đã lấy token từ session:")
	print(f"  User: {user_name}")
	print(f"  Email: {user_email}")
	print(f"  Hết hạn: {expires_vn}")
	
	token = data.get("access_token")
	if isinstance(token, str) and token:
		return token
	return None


def sanitize_filename(filename: str) -> str:
	"""Làm sạch tên file để tránh ký tự không hợp lệ"""
	# Loại bỏ ký tự không hợp lệ cho tên file
	filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
	# Loại bỏ ký tự xuống dòng và tab
	filename = re.sub(r'[\n\r\t]', '_', filename)
	# Loại bỏ khoảng trắng thừa
	filename = re.sub(r'\s+', ' ', filename)
	# Giới hạn độ dài tên file (Windows có giới hạn 255 ký tự cho đường dẫn đầy đủ)
	# Để an toàn, giới hạn ở 100 ký tự cho tên file
	if len(filename) > 100:
		filename = filename[:100]
	return filename.strip()


def create_short_filename(stt: int, prompt: str) -> str:
	"""Tạo tên file ngắn gọn từ STT và prompt"""
	# Lấy 50 ký tự đầu của prompt và làm sạch
	short_prompt = prompt[:50].strip()
	short_prompt = sanitize_filename(short_prompt)
	
	# Tạo tên file với format: STT_short_description.mp4
	filename = f"{stt}_{short_prompt}.mp4"
	
	# Đảm bảo tên file không quá dài
	if len(filename) > 100:
		# Nếu vẫn quá dài, chỉ lấy STT và một phần nhỏ của prompt
		short_prompt = short_prompt[:30]
		filename = f"{stt}_{short_prompt}.mp4"
	
	return filename


def read_excel_prompts(excel_file: str, require_image: bool = False) -> List[Tuple[int, str, Optional[str]]]:
	"""Đọc file Excel và trả về danh sách (STT, PROMPT, IMAGE_PATH)"""
	try:
		df = pd.read_excel(excel_file)
		
		# Kiểm tra số cột
		if require_image:
			# Chế độ Image + prompt cần đủ 3 cột
			if len(df.columns) < 3:
				print(f"\n❌ Lỗi: File Excel hiện tại chỉ có {len(df.columns)} cột")
				print("📋 Chế độ Image + prompt cần đủ 3 cột:")
				print("   Cột A: STT (1, 2, 3...)")
				print("   Cột B: PROMPT (mô tả video)")
				print("   Cột C: IMAGE_PATH (đường dẫn file image)")
				print("\n💡 Hướng dẫn:")
				print("   1. Mở file Excel")
				print("   2. Thêm cột C với tiêu đề 'IMAGE_PATH'")
				print("   3. Điền đường dẫn file image cho từng dòng")
				print("   4. Chạy lại chương trình")
				raise ValueError("File Excel thiếu cột IMAGE_PATH. Vui lòng thêm cột C với đường dẫn image.")
			print("✓ Kiểm tra Excel: Đủ 3 cột (STT, PROMPT, IMAGE_PATH)")
		else:
			# Chế độ text-only cần ít nhất 2 cột
			if len(df.columns) < 2:
				print(f"\n❌ Lỗi: File Excel hiện tại chỉ có {len(df.columns)} cột")
				print("📋 Chế độ text-only cần ít nhất 2 cột:")
				print("   Cột A: STT (1, 2, 3...)")
				print("   Cột B: PROMPT (mô tả video)")
				raise ValueError("File Excel thiếu cột PROMPT. Vui lòng thêm cột B với prompt.")
			print("✓ Kiểm tra Excel: Đủ 2 cột (STT, PROMPT)")
		
		prompts = []
		missing_images = []
		
		for index, row in df.iterrows():
			stt = row.iloc[0]  # Cột A
			prompt = row.iloc[1]  # Cột B
			image_path = row.iloc[2] if len(df.columns) > 2 else None  # Cột C (nếu có)
			
			# Bỏ qua dòng trống hoặc không hợp lệ
			if pd.isna(stt) or pd.isna(prompt):
				continue
			
			# Chuyển đổi STT thành int
			try:
				stt_int = int(stt)
			except (ValueError, TypeError):
				print(f"Cảnh báo: STT '{stt}' không hợp lệ, bỏ qua dòng {index + 1}")
				continue
			
			# Xử lý image_path
			image_path_str = None
			if not pd.isna(image_path) and str(image_path).strip():
				image_path_str = str(image_path).strip()
			
			# Kiểm tra image path nếu yêu cầu
			if require_image:
				if not image_path_str:
					missing_images.append(f"Dòng {index + 1} (STT {stt_int}): Thiếu đường dẫn image")
					continue
				if not os.path.exists(image_path_str):
					missing_images.append(f"Dòng {index + 1} (STT {stt_int}): File image không tồn tại: {image_path_str}")
					continue
				if not image_path_str.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
					missing_images.append(f"Dòng {index + 1} (STT {stt_int}): File image không đúng định dạng: {image_path_str}")
					continue
			
			prompts.append((stt_int, str(prompt).strip(), image_path_str))
		
		# Báo cáo kết quả kiểm tra
		if require_image and missing_images:
			print(f"\n❌ Lỗi kiểm tra Excel:")
			for error in missing_images:
				print(f"  {error}")
			raise ValueError(f"Có {len(missing_images)} lỗi trong file Excel. Vui lòng sửa trước khi tiếp tục.")
		
		if require_image:
			print(f"✓ Kiểm tra Excel: Tất cả {len(prompts)} dòng đều có image hợp lệ")
		else:
			print(f"✓ Kiểm tra Excel: Đã đọc {len(prompts)} prompt")
		
		return prompts
		
	except FileNotFoundError:
		print(f"\n❌ Lỗi: Không tìm thấy file Excel: {excel_file}")
		exit(1)
	except ValueError as e:
		print(f"\n❌ Lỗi: {e}")
		exit(1)
	except Exception as e:
		print(f"\n❌ Lỗi đọc file Excel: {e}")
		exit(1)

