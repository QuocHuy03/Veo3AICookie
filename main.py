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
import sys
import requests
import pandas as pd

from auth.auth_guard import check_key_online
API_URL = "http://62.171.131.164:5000"
GENERATE_URL = "https://aisandbox-pa.googleapis.com/v1/video:batchAsyncGenerateVideoText"
GENERATE_IMAGE_URL = "https://aisandbox-pa.googleapis.com/v1/video:batchAsyncGenerateVideoStartImage"
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


def get_fake_fingerprint() -> Dict[str, str]:
	"""Tạo fingerprint giả lập"""
	return {
		"X-Client-Data": "CJW2yQEIpLbJAQjBtskBCKmdygE=",
		"X-Goog-Api-Key": "AIzaSyBvQZgjXvJ8QJ8QJ8QJ8QJ8QJ8QJ8QJ8QJ8",
		"X-Goog-AuthUser": "0",
		"X-Goog-PageId": str(random.randint(1000000, 9999999)),
		"X-Goog-Request-Id": str(uuid.uuid4()),
		"X-Goog-User-Project": "labs-ai-sandbox",
		"X-Origin": "https://labs.google",
		"X-Referer": "https://labs.google/",
		"X-Requested-With": "XMLHttpRequest"
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
				print(f"Request URL: {url}")
				print(f"Request Headers: {dict(session.headers)}")
			raise


def http_download(url: str, output_path: str, proxy: Optional[Dict[str, str]] = None) -> None:
	headers = get_browser_headers()
	session = requests.Session()
	session.headers.update(headers)
	
	with session.get(url, stream=True, timeout=120, proxies=proxy) as r:
		r.raise_for_status()
		with open(output_path, "wb") as f:
			for chunk in r.iter_content(chunk_size=1024 * 1024):
				if chunk:
					f.write(chunk)


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



def _read_token_from_file(path: str) -> Optional[str]:
	try:
		with open(path, "r", encoding="utf-8") as f:
			content = f.read().strip().strip('\ufeff')
			return content or None
	except FileNotFoundError:
		return None


def _read_cookie_header_from_file(path: str) -> Optional[str]:
	try:
		with open(path, "r", encoding="utf-8") as f:
			content = f.read().strip().strip('\ufeff')
			if not content:
				return None
			if content.lower().startswith("cookie:"):
				return content.split(":", 1)[1].strip()
			return content
	except FileNotFoundError:
		return None


def _test_proxy_connection(proxy: Dict[str, str], timeout: int = 10) -> bool:
	"""Test kết nối proxy bằng cách gọi một URL đơn giản"""
	try:
		session = requests.Session()
		session.proxies.update(proxy)
		# Test với một URL đơn giản
		response = session.get("https://httpbin.org/ip", timeout=timeout)
		if response.status_code == 200:
			print("✓ Proxy connection test thành công")
			return True
		else:
			print(f"⚠ Proxy test failed với status: {response.status_code}")
			return False
	except Exception as e:
		print(f"❌ Proxy connection test thất bại: {e}")
		return False


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


def _read_proxy_from_file(path: str, test_connection: bool = True) -> Optional[Dict[str, str]]:
	"""Đọc proxy từ file proxy.txt và trả về dict proxy cho requests"""
	try:
		with open(path, "r", encoding="utf-8") as f:
			content = f.read().strip().strip('\ufeff')
			if not content:
				return None
			
			# Format: ip:port:username:password
			parts = content.split(":")
			if len(parts) != 4:
				print(f"⚠ Cảnh báo: Format proxy không đúng trong {path}. Cần: ip:port:username:password")
				return None
			
			ip, port, username, password = parts
			
			# Validate IP và port
			try:
				int(port)
			except ValueError:
				print(f"⚠ Cảnh báo: Port không hợp lệ: {port}")
				return None
			
			# Tạo proxy dict cho requests
			proxy_url = f"http://{username}:{password}@{ip}:{port}"
			proxy_dict = {
				"http": proxy_url,
				"https": proxy_url
			}
			
			print(f"✓ Đã tải proxy: {ip}:{port}")
			
			# Test connection nếu được yêu cầu
			if test_connection:
				if not _test_proxy_connection(proxy_dict):
					print("⚠ Proxy không hoạt động, sẽ chạy không proxy")
					return None
			
			return proxy_dict
	except FileNotFoundError:
		print(f"⚠ Không tìm thấy file proxy: {path}")
		return None
	except Exception as e:
		print(f"❌ Lỗi đọc file proxy: {e}")
		return None


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


def process_single_prompt(args: Tuple[int, str, Optional[str], str, str, str, str, Optional[Dict[str, str]], Optional[str]]) -> Tuple[int, str, bool, str]:
	"""Xử lý một prompt đơn lẻ trong thread riêng với auto retry"""
	stt, prompt, image_path, token, project_id, model_key, output_dir, proxy, cookie_header_value = args
	
	# Đọc cấu hình retry từ config
	config = _load_config()
	retry_config = config.get("auto_retry", {})
	enable_auto_retry = retry_config.get("enable_auto_retry", True)
	max_retries = retry_config.get("max_retries", 3)
	base_delay = retry_config.get("base_delay", 2.0)
	max_delay = retry_config.get("max_delay", 30.0)
	backoff_factor = retry_config.get("backoff_factor", 2.0)
	
	def _process_prompt_internal():
		"""Hàm internal để retry"""
		print(f"[Thread {threading.current_thread().name}] Bắt đầu xử lý STT {stt}: {prompt[:50]}...")
		
		# Tạo tên file output ngắn gọn
		output_filename = create_short_filename(stt, prompt)
		output_path = os.path.join(output_dir, output_filename)
		
		# Generate video
		if image_path and os.path.exists(image_path):
			# Có image - upload image trước, rồi generate video từ image + prompt
			print(f"[Thread {threading.current_thread().name}] Upload image: {image_path}")
			media_id = upload_image(token, image_path, proxy)
			print(f"[Thread {threading.current_thread().name}] ✅ Upload thành công - Media ID: {media_id}")
			
			# Generate video từ image + prompt
			print(f"[Thread {threading.current_thread().name}] 🎬 Bắt đầu tạo video từ image + prompt...")
			gen_resp, scene_id = generate_video_from_image(token, prompt, media_id, project_id, model_key, proxy=proxy)
		else:
			# Không có image - generate video từ prompt only
			print(f"[Thread {threading.current_thread().name}] 🎬 Bắt đầu tạo video từ prompt...")
			gen_resp, scene_id = generate_video(token, prompt, project_id, model_key, proxy=proxy)
			media_id = None
		
		op_name = extract_op_name(gen_resp)
		
		# Poll status
		print(f"[Thread {threading.current_thread().name}] ⏳ Đang chờ video được tạo...")
		status_resp = poll_status(token, op_name, scene_id, proxy=proxy)
		
		# Download video trực tiếp dưới dạng MP4
		print(f"[Thread {threading.current_thread().name}] 📥 Đang tải video...")
		fife_url = extract_fife_url(status_resp)
		http_download_mp4(fife_url, output_path, proxy)
		
		# Sau khi tải xong, nếu có media_id (luồng image), thực hiện xóa media trên server
		try:
			if media_id and cookie_header_value:
				print(f"[Thread {threading.current_thread().name}] 🧹 Xóa media tạm trên server...")
				delete_media([media_id], cookie_header_value, proxy)
		except Exception as e:
			print(f"[Thread {threading.current_thread().name}] ⚠ Không thể xóa media: {e}")
		
		print(f"[Thread {threading.current_thread().name}] ✅ Hoàn thành STT {stt}: {output_filename}")
		return (stt, prompt, True, output_filename)
	
	try:
		if enable_auto_retry:
			# Sử dụng auto retry với cấu hình từ config
			return auto_retry_with_backoff(
				_process_prompt_internal,
				max_retries=max_retries,
				base_delay=base_delay,
				max_delay=max_delay,
				backoff_factor=backoff_factor,
				retry_on_exceptions=(
					requests.exceptions.RequestException,
					requests.exceptions.Timeout,
					requests.exceptions.ConnectionError,
					requests.exceptions.HTTPError,
					Exception  # Có thể retry với mọi exception
				)
			)
		else:
			# Không sử dụng auto retry, chạy trực tiếp
			return _process_prompt_internal()
	except Exception as e:
		print(f"[Thread {threading.current_thread().name}] ❌ Lỗi xử lý STT {stt} sau khi retry: {e}")
		return (stt, prompt, False, str(e))


def process_single_prompt_batch(prompt: str, token: str, project_id: str, 
                               model_key: str = "veo_3_0_t2v_fast_ultra", 
                               max_workers: int = 5, output_dir: str = "output", 
                               proxy: Optional[Dict[str, str]] = None,
                               cookie_header_value: Optional[str] = None) -> None:
	"""Xử lý một prompt duy nhất nhưng tạo nhiều video với đa luồng"""
	
	# Đọc cấu hình retry để hiển thị thông tin
	config = _load_config()
	retry_config = config.get("auto_retry", {})
	enable_auto_retry = retry_config.get("enable_auto_retry", True)
	max_retries = retry_config.get("max_retries", 3)
	
	# Tạo thư mục output nếu chưa có
	os.makedirs(output_dir, exist_ok=True)
	
	# Tạo danh sách prompts giống nhau để xử lý song song
	prompts = [(i+1, prompt, None) for i in range(max_workers)]
	
	print(f"Bắt đầu xử lý prompt '{prompt}' với {max_workers} luồng...")
	if enable_auto_retry:
		print(f"🔄 Auto retry: BẬT (tối đa {max_retries} lần retry cho mỗi prompt)")
	else:
		print(f"🔄 Auto retry: TẮT")
	
	# Chuẩn bị arguments cho mỗi thread
	args_list = [
		(stt, prompt, image_path, token, project_id, model_key, output_dir, proxy, cookie_header_value)
		for stt, prompt, image_path in prompts
	]
	
	# Xử lý với ThreadPoolExecutor
	results = []
	with ThreadPoolExecutor(max_workers=max_workers) as executor:
		# Submit tất cả tasks
		future_to_args = {executor.submit(process_single_prompt, args): args for args in args_list}
		
		# Thu thập kết quả
		for future in as_completed(future_to_args):
			args = future_to_args[future]
			try:
				result = future.result()
				results.append(result)
			except Exception as e:
				stt, prompt = args[0], args[1]
				print(f"Lỗi không mong đợi với STT {stt}: {e}")
				results.append((stt, prompt, False, str(e)))
	
	# Báo cáo kết quả
	successful = [r for r in results if r[2]]
	failed = [r for r in results if not r[2]]
	
	print(f"\n=== KẾT QUẢ XỬ LÝ ===")
	print(f"Thành công: {len(successful)}/{len(results)}")
	print(f"Thất bại: {len(failed)}/{len(results)}")
	
	if successful:
		print(f"\nCác file đã tạo thành công:")
		for stt, prompt, _, filename in successful:
			print(f"  STT {stt}: {filename}")
	
	if failed:
		print(f"\nCác prompt thất bại:")
		for stt, prompt, _, error in failed:
			print(f"  STT {stt}: {error}")


def process_single_image_batch(prompt: str, image_path: str, token: str, project_id: str, 
                              model_key: str = "veo_3_i2v_s_fast_ultra", 
                              max_workers: int = 5, output_dir: str = "output", 
                              proxy: Optional[Dict[str, str]] = None,
                              cookie_header_value: Optional[str] = None) -> None:
	"""Xử lý một prompt + image duy nhất nhưng tạo nhiều video với đa luồng"""
	
	# Đọc cấu hình retry để hiển thị thông tin
	config = _load_config()
	retry_config = config.get("auto_retry", {})
	enable_auto_retry = retry_config.get("enable_auto_retry", True)
	max_retries = retry_config.get("max_retries", 3)
	
	# Tạo thư mục output nếu chưa có
	os.makedirs(output_dir, exist_ok=True)
	
	# Tạo danh sách prompts giống nhau để xử lý song song
	prompts = [(i+1, prompt, image_path) for i in range(max_workers)]
	
	print(f"Bắt đầu xử lý prompt '{prompt}' với image '{image_path}' và {max_workers} luồng...")
	if enable_auto_retry:
		print(f"🔄 Auto retry: BẬT (tối đa {max_retries} lần retry cho mỗi prompt)")
	else:
		print(f"🔄 Auto retry: TẮT")
	
	# Chuẩn bị arguments cho mỗi thread
	args_list = [
		(stt, prompt, image_path, token, project_id, model_key, output_dir, proxy, cookie_header_value)
		for stt, prompt, image_path in prompts
	]
	
	# Xử lý với ThreadPoolExecutor
	results = []
	with ThreadPoolExecutor(max_workers=max_workers) as executor:
		# Submit tất cả tasks
		future_to_args = {executor.submit(process_single_prompt, args): args for args in args_list}
		
		# Thu thập kết quả
		for future in as_completed(future_to_args):
			args = future_to_args[future]
			try:
				result = future.result()
				results.append(result)
			except Exception as e:
				stt, prompt = args[0], args[1]
				print(f"Lỗi không mong đợi với STT {stt}: {e}")
				results.append((stt, prompt, False, str(e)))
	
	# Báo cáo kết quả
	successful = [r for r in results if r[2]]
	failed = [r for r in results if not r[2]]
	
	print(f"\n=== KẾT QUẢ XỬ LÝ ===")
	print(f"Thành công: {len(successful)}/{len(results)}")
	print(f"Thất bại: {len(failed)}/{len(results)}")
	
	if successful:
		print(f"\nCác file đã tạo thành công:")
		for stt, prompt, _, filename in successful:
			print(f"  STT {stt}: {filename}")
	
	if failed:
		print(f"\nCác prompt thất bại:")
		for stt, prompt, _, error in failed:
			print(f"  STT {stt}: {error}")


def process_excel_batch(excel_file: str, token: str, project_id: str, 
                       model_key: str = "veo_3_0_t2v_fast_ultra", 
                       max_workers: int = 5, output_dir: str = "output", 
                       require_image: bool = False, proxy: Optional[Dict[str, str]] = None, 
                       cookie_header_value: Optional[str] = None) -> None:
	"""Xử lý batch từ file Excel với đa luồng"""
	
	# Đọc cấu hình retry để hiển thị thông tin
	config = _load_config()
	retry_config = config.get("auto_retry", {})
	enable_auto_retry = retry_config.get("enable_auto_retry", True)
	max_retries = retry_config.get("max_retries", 3)
	
	# Tạo thư mục output nếu chưa có
	os.makedirs(output_dir, exist_ok=True)
	
	# Đọc prompts từ Excel với kiểm tra image nếu cần
	try:
		prompts = read_excel_prompts(excel_file, require_image)
	except SystemExit:
		return  # Đã hiển thị lỗi và thoát trong read_excel_prompts
	
	if not prompts:
		print("Không có prompt nào để xử lý")
		return
	
	print(f"Bắt đầu xử lý {len(prompts)} prompt với {max_workers} luồng...")
	if enable_auto_retry:
		print(f"🔄 Auto retry: BẬT (tối đa {max_retries} lần retry cho mỗi prompt)")
	else:
		print(f"🔄 Auto retry: TẮT")
	
	# Chuẩn bị arguments cho mỗi thread
	args_list = [
		(stt, prompt, image_path, token, project_id, model_key, output_dir, proxy, cookie_header_value)
		for stt, prompt, image_path in prompts
	]
	
	# Xử lý với ThreadPoolExecutor
	results = []
	with ThreadPoolExecutor(max_workers=max_workers) as executor:
		# Submit tất cả tasks
		future_to_args = {executor.submit(process_single_prompt, args): args for args in args_list}
		
		# Thu thập kết quả
		for future in as_completed(future_to_args):
			args = future_to_args[future]
			try:
				result = future.result()
				results.append(result)
			except Exception as e:
				stt, prompt = args[0], args[1]
				print(f"Lỗi không mong đợi với STT {stt}: {e}")
				results.append((stt, prompt, False, str(e)))
	
	# Báo cáo kết quả
	successful = [r for r in results if r[2]]
	failed = [r for r in results if not r[2]]
	
	print(f"\n=== KẾT QUẢ XỬ LÝ ===")
	print(f"Thành công: {len(successful)}/{len(results)}")
	print(f"Thất bại: {len(failed)}/{len(results)}")
	
	if successful:
		print(f"\nCác file đã tạo thành công:")
		for stt, prompt, _, filename in successful:
			print(f"  STT {stt}: {filename}")
	
	if failed:
		print(f"\nCác prompt thất bại:")
		for stt, prompt, _, error in failed:
			print(f"  STT {stt}: {error}")


def get_user_input():
	"""Lấy input từ người dùng qua command line"""
	print("=== CẤU HÌNH XỬ LÝ VIDEO ===")
	
	# Chọn chế độ
	print("\n1. Prompt to video (text-only)")
	print("2. Image + prompt to video")
	
	while True:
		try:
			mode = input("\nChọn chế độ (1 hoặc 2): ").strip()
			if mode in ["1", "2"]:
				break
			else:
				print("Vui lòng chọn 1 hoặc 2")
		except KeyboardInterrupt:
			print("\nĐã hủy bởi người dùng")
			exit(0)
	
	if mode == "1":
		# Chế độ Prompt to video (text-only)
		# Hỏi xem muốn xử lý Excel hay đơn lẻ
		print("\nChọn cách xử lý:")
		print("a. Xử lý từ file Excel (nhiều prompt)")
		print("b. Xử lý đơn lẻ (1 prompt)")
		
		while True:
			sub_mode = input("\nChọn (a hoặc b): ").strip().lower()
			if sub_mode in ["a", "b"]:
				break
			else:
				print("Vui lòng chọn a hoặc b")
		
		if sub_mode == "a":
			# Excel mode
			while True:
				excel_file = input("\nNhập đường dẫn file Excel: ").strip()
				if not excel_file:
					print("Vui lòng nhập đường dẫn file Excel")
					continue
				if not os.path.exists(excel_file):
					print(f"File không tồn tại: {excel_file}")
					continue
				if not excel_file.lower().endswith(('.xlsx', '.xls')):
					print("File phải có định dạng .xlsx hoặc .xls")
					continue
				break
			
			while True:
				try:
					max_workers_input = input("\nNhập số luồng xử lý (mặc định 5): ").strip()
					if not max_workers_input:
						max_workers = 5
						break
					max_workers = int(max_workers_input)
					if max_workers < 1 or max_workers > 20:
						print("Số luồng phải từ 1 đến 20")
						continue
					break
				except ValueError:
					print("Vui lòng nhập số nguyên hợp lệ")
			
			output_dir = input("\nNhập thư mục output (mặc định 'output'): ").strip()
			if not output_dir:
				output_dir = "output"
			
			return {
				"mode": "excel",
				"excel_file": excel_file,
				"max_workers": max_workers,
				"output_dir": output_dir
			}
		else:
			# Single mode - nhưng vẫn dùng đa luồng
			prompt = input("\nNhập prompt: ").strip()
			if not prompt:
				prompt = "Kaela standing before the mysterious pod..."
			
			while True:
				try:
					max_workers_input = input("\nNhập số luồng xử lý (mặc định 5): ").strip()
					if not max_workers_input:
						max_workers = 5
						break
					max_workers = int(max_workers_input)
					if max_workers < 1 or max_workers > 20:
						print("Số luồng phải từ 1 đến 20")
						continue
					break
				except ValueError:
					print("Vui lòng nhập số nguyên hợp lệ")
			
			output_dir = input("\nNhập thư mục output (mặc định 'output'): ").strip()
			if not output_dir:
				output_dir = "output"
			
			return {
				"mode": "single_batch",
				"prompt": prompt,
				"max_workers": max_workers,
				"output_dir": output_dir
			}
	else:
		# Chế độ Image + prompt to video
		# Hỏi xem muốn xử lý Excel hay đơn lẻ
		print("\nChọn cách xử lý:")
		print("a. Xử lý từ file Excel (nhiều prompt + image)")
		print("b. Xử lý đơn lẻ (1 prompt + 1 image)")
		
		while True:
			sub_mode = input("\nChọn (a hoặc b): ").strip().lower()
			if sub_mode in ["a", "b"]:
				break
			else:
				print("Vui lòng chọn a hoặc b")
		
		if sub_mode == "a":
			# Excel mode với image
			while True:
				excel_file = input("\nNhập đường dẫn file Excel: ").strip()
				if not excel_file:
					print("Vui lòng nhập đường dẫn file Excel")
					continue
				if not os.path.exists(excel_file):
					print(f"File không tồn tại: {excel_file}")
					continue
				if not excel_file.lower().endswith(('.xlsx', '.xls')):
					print("File phải có định dạng .xlsx hoặc .xls")
					continue
				break
			
			while True:
				try:
					max_workers_input = input("\nNhập số luồng xử lý (mặc định 5): ").strip()
					if not max_workers_input:
						max_workers = 5
						break
					max_workers = int(max_workers_input)
					if max_workers < 1 or max_workers > 20:
						print("Số luồng phải từ 1 đến 20")
						continue
					break
				except ValueError:
					print("Vui lòng nhập số nguyên hợp lệ")
			
			output_dir = input("\nNhập thư mục output (mặc định 'output'): ").strip()
			if not output_dir:
				output_dir = "output"
			
			return {
				"mode": "excel_image",
				"excel_file": excel_file,
				"max_workers": max_workers,
				"output_dir": output_dir
			}
		else:
			# Single mode với image - nhưng vẫn dùng đa luồng
			prompt = input("\nNhập prompt: ").strip()
			if not prompt:
				prompt = "A beautiful sunset over the ocean"
			
			while True:
				image_path = input("\nNhập đường dẫn file image: ").strip()
				if not image_path:
					print("Vui lòng nhập đường dẫn file image")
					continue
				if not os.path.exists(image_path):
					print(f"File không tồn tại: {image_path}")
					continue
				if not image_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
					print("File phải có định dạng .jpg, .jpeg, .png, .gif hoặc .webp")
					continue
				break
			
			while True:
				try:
					max_workers_input = input("\nNhập số luồng xử lý (mặc định 5): ").strip()
					if not max_workers_input:
						max_workers = 5
						break
					max_workers = int(max_workers_input)
					if max_workers < 1 or max_workers > 20:
						print("Số luồng phải từ 1 đến 20")
						continue
					break
				except ValueError:
					print("Vui lòng nhập số nguyên hợp lệ")
			
			output_dir = input("\nNhập thư mục output (mặc định 'output'): ").strip()
			if not output_dir:
				output_dir = "output"
			
			return {
				"mode": "single_image_batch",
				"prompt": prompt,
				"image_path": image_path,
				"max_workers": max_workers,
				"output_dir": output_dir
			}


def main():

	text = r"""
 __     _______ ___    _____      _    ___ 
 \ \   / / ____/ _ \  |___ /     / \  |_ _|
  \ \ / /|  _|| | | |   |_ \    / _ \  | | 
   \ V / | |__| |_| |  ___) |  / ___ \ | | 
    \_/  |_____\___/  |____/  /_/   \_\___|
	"""
	print(text)

	# Input qua env hoặc file
	token = os.getenv("AISANDBOX_TOKEN") or ""
	token_file = os.getenv("AISANDBOX_TOKEN_FILE") or "token.txt"
	cookie_file = os.getenv("AISANDBOX_COOKIE_FILE") or "cookie.txt"
	if not token:
		file_token = _read_token_from_file(token_file)
		if file_token:
			token = file_token
	# Nếu vẫn chưa có token, thử gọi session bằng cookie.txt
	if not token:
		cookie_header_value = _read_cookie_header_from_file(cookie_file)
		if cookie_header_value:
			try:
				# Đọc proxy tạm thời để lấy token (không test connection để tránh delay)
				proxy_file = os.getenv("AISANDBOX_PROXY_FILE") or "proxy.txt"
				temp_proxy = _read_proxy_from_file(proxy_file, test_connection=False)
				session_token = fetch_access_token_from_session(cookie_header_value, temp_proxy)
				if session_token:
					token = session_token
			except requests.HTTPError:
				pass

	if not token:
		raise RuntimeError("Thiếu token. Đặt AISANDBOX_TOKEN hoặc tạo file token.txt")

	# Cấu hình chung
	config = _load_config()
	project_id = os.getenv("AISANDBOX_PROJECT_ID") or config.get("project_id", "66a1a7a3-c9d9-4c42-a07e-44f2baecf60b")
	model_key = os.getenv("AISANDBOX_MODEL_KEY") or config.get("model_key", "veo_3_0_t2v_fast_ultra")
	
	# Đọc proxy từ file với test connection
	proxy_file = os.getenv("AISANDBOX_PROXY_FILE") or "proxy.txt"
	proxy = _read_proxy_from_file(proxy_file, test_connection=True)
	if proxy:
		print("✓ Đã tải và test proxy thành công")
	else:
		print("⚠ Không sử dụng proxy (file không tồn tại hoặc proxy không hoạt động)")
	
	# Thông báo về các thông số giả lập
	print("✓ Đã kích hoạt các thông số giả lập trình duyệt thật:")
	print("  - User-Agent ngẫu nhiên")
	print("  - Headers giả lập trình duyệt")
	print("  - Fingerprint giả lập")
	print("  - Delay ngẫu nhiên giữa các request")
	print("  - Session giả lập")
	
	# Lấy input từ người dùng
	user_config = get_user_input()
	
	if user_config["mode"] == "excel":
		# Chế độ Excel - xử lý batch
		excel_file = user_config["excel_file"]
		max_workers = user_config["max_workers"]
		output_dir = user_config["output_dir"]
		
		print(f"\n=== BẮT ĐẦU XỬ LÝ ===")
		print(f"File Excel: {excel_file}")
		print(f"Số luồng: {max_workers}")
		print(f"Thư mục output: {output_dir}")
		
		process_excel_batch(excel_file, token, project_id, model_key, max_workers, output_dir, require_image=False, proxy=proxy, cookie_header_value=cookie_header_value)
	elif user_config["mode"] == "excel_image":
		# Chế độ Excel với image - xử lý batch
		excel_file = user_config["excel_file"]
		max_workers = user_config["max_workers"]
		output_dir = user_config["output_dir"]
		
		print(f"\n=== BẮT ĐẦU XỬ LÝ ===")
		print(f"File Excel: {excel_file}")
		print(f"Số luồng: {max_workers}")
		print(f"Thư mục output: {output_dir}")
		
		process_excel_batch(excel_file, token, project_id, "veo_3_i2v_s_fast_ultra", max_workers, output_dir, require_image=True, proxy=proxy, cookie_header_value=cookie_header_value)
	elif user_config["mode"] == "single_batch":
		# Chế độ đơn lẻ với đa luồng - xử lý một prompt (text only)
		prompt = user_config["prompt"]
		max_workers = user_config["max_workers"]
		output_dir = user_config["output_dir"]

		print(f"\n=== BẮT ĐẦU XỬ LÝ ===")
		print(f"Prompt: {prompt}")
		print(f"Số luồng: {max_workers}")
		print(f"Thư mục output: {output_dir}")

		process_single_prompt_batch(prompt, token, project_id, model_key, max_workers, output_dir, proxy=proxy, cookie_header_value=cookie_header_value)
	elif user_config["mode"] == "single_image_batch":
		# Chế độ đơn lẻ với image và đa luồng - xử lý một prompt + image
		prompt = user_config["prompt"]
		image_path = user_config["image_path"]
		max_workers = user_config["max_workers"]
		output_dir = user_config["output_dir"]

		print(f"\n=== BẮT ĐẦU XỬ LÝ ===")
		print(f"Prompt: {prompt}")
		print(f"Image: {image_path}")
		print(f"Số luồng: {max_workers}")
		print(f"Thư mục output: {output_dir}")

		process_single_image_batch(prompt, image_path, token, project_id, "veo_3_i2v_s_fast_ultra", max_workers, output_dir, proxy=proxy, cookie_header_value=cookie_header_value)


# === UTILITY FUNCTIONS ===
def ensure_dir(path):
    """Ensure directory exists"""
    if not os.path.exists(path):
        os.makedirs(path)

def center_line(text, width=70):
    """Center text within given width"""
    return text.center(width)

def print_box(info):
    """Print authentication info in a formatted box"""
    box_width = 70
    print("╔" + "═" * (box_width - 2) + "╗")
    print("║" + center_line("🔐 XÁC THỰC KEY THÀNH CÔNG", box_width - 2) + "║")
    print("╠" + "═" * (box_width - 2) + "╣")
    print("║" + center_line(f"🔑 KEY       : {info.get('key')}", box_width - 2) + "║")
    print("║" + center_line(f"📅 Hết hạn    : {info.get('expires')}", box_width - 2) + "║")
    print("║" + center_line(f"🔁 Số lượt    : {info.get('remaining')}", box_width - 2) + "║")
    print("╠" + "═" * (box_width - 2) + "╣")
    print("║" + center_line("🧠 Info dev @huyit32", box_width - 2) + "║")
    print("║" + center_line("📧 qhuy.dev@gmail.com", box_width - 2) + "║")
    print("╚" + "═" * (box_width - 2) + "╝")

# === MAIN EXECUTION ===
if __name__ == "__main__":
    API_AUTH = f"{API_URL}/api/make_video_ai/auth"
    MAX_RETRIES = 5

    print("\n📌 XÁC THỰC KEY ĐỂ SỬ DỤNG CÔNG CỤ - VEO3 AI\n")

    for attempt in range(1, MAX_RETRIES + 1):
        key = input(f"🔑 Nhập API Key (Lần {attempt}/{MAX_RETRIES}): ").strip()
        success, message, info = check_key_online(key, API_AUTH)

        if success:
            print("\n" + message + "\n")
            print_box(info)
            print()

            run_now = input("▶️  Bạn có muốn chạy chương trình ngay bây giờ không? (Y/n): ").strip().lower()
            if run_now in ("", "y", "yes"):
                print("🚀 Khởi động VEO3 AI...")
                main()
            else:
                print("✋ Bạn đã chọn không chạy chương trình. Thoát.")
            break
        else:
            print(f"\n {message}")
            if attempt < MAX_RETRIES:
                print("↩️  Vui lòng thử lại...\n")
                time.sleep(1)
            else:
                print("\n🚫 Đã nhập sai quá 5 lần. Thoát chương trình.")
                print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                print("🧠 Info dev @huyit32 | 📧 qhuy.dev@gmail.com")
                print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                sys.exit(1)