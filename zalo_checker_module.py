from venv import logger
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
import random
import logging
from typing import List, Dict, Optional, Tuple
import json
import requests
from fp.fp import FreeProxy

class ZaloChecker:
    def __init__(self, headless: bool = False, log_widget=None, use_proxy: bool = False, proxy_list: List[str] = None):
        """Khởi tạo trình duyệt với các tùy chọn, bao gồm proxy"""
        self.log_widget = log_widget
        self.headless = headless
        self.search_count = 0
        self.last_search_time = 0
        self.use_proxy = use_proxy
        self.proxy_list = proxy_list or []
        self.current_proxy_index = 0
        self.limit_count = 0
        self.session_start_time = time.time()
        
        # Thiết lập logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Khởi tạo trình duyệt
        self.init_driver()
        
        self.wait = WebDriverWait(self.driver, 15)
        self.results: List[Dict] = []
        
    def init_driver(self):
        """Khởi tạo trình duyệt với cấu hình proxy nếu được yêu cầu"""
        options = webdriver.ChromeOptions()
        
        if self.headless:
            options.add_argument('--headless=new')  # Sử dụng headless mới
        
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Thêm các tùy chọn để tránh bị phát hiện
        options.add_argument('--disable-web-security')
        options.add_argument('--allow-running-insecure-content')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-software-rasterizer')
        
        # Thiết lập user-agent ngẫu nhiên
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
        ]
        options.add_argument(f'--user-agent={random.choice(user_agents)}')
        
        # Xử lý proxy nếu được kích hoạt
        if self.use_proxy and self.proxy_list:
            proxy = self.get_next_proxy()
            if proxy:
                options.add_argument(f'--proxy-server={proxy}')
                self.log_message(f"Đang sử dụng proxy: {proxy}")
        
        # Khởi tạo driver
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options
            )
        except:
            # Fallback nếu không dùng được webdriver_manager
            self.driver = webdriver.Chrome(options=options)
        
        # Ẩn thông tin automation
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
                window.chrome = {
                    runtime: {},
                };
            '''
        })
        
        # Thiết lập window size ngẫu nhiên
        width = random.randint(1200, 1920)
        height = random.randint(800, 1080)
        self.driver.set_window_size(width, height)
        
        # Di chuyển window position ngẫu nhiên
        x = random.randint(0, 100)
        y = random.randint(0, 100)
        self.driver.set_window_position(x, y)
    
    def get_next_proxy(self):
        """Lấy proxy tiếp theo từ danh sách"""
        if not self.proxy_list:
            return None
            
        proxy = self.proxy_list[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)
        return proxy
    
    def rotate_proxy(self):
        """Xoay proxy để tránh bị chặn"""
        if not self.use_proxy or not self.proxy_list:
            return False
            
        self.log_message("Đang xoay proxy...")
        self.close()
        time.sleep(2)
        self.init_driver()
        
        # Truy cập lại trang Zalo
        try:
            self.driver.get("https://chat.zalo.me/")
            time.sleep(3)
            return True
        except:
            self.log_message("Lỗi khi xoay proxy")
            return False
    
    def log_message(self, message):
        """Ghi log message ra cả console và widget log nếu có"""
        print(message)
        self.logger.info(message)
        if self.log_widget:
            self.log_widget(f"[ZaloChecker] {message}")
    
    def human_like_delay(self, min_delay: float = 1, max_delay: float = 3):
        """Tạo delay ngẫu nhiên giống hành vi người dùng thực với thời gian dài hơn"""
        current_time = time.time()
        time_since_last_search = current_time - self.last_search_time
        
        # Tính toán thời gian chờ còn lại cần thiết
        required_wait = max(0, min_delay - time_since_last_search)
        if required_wait > 0:
            self.log_message(f"Chờ thêm {required_wait:.1f}s để đảm bảo khoảng cách giữa các lần tìm kiếm")
            time.sleep(required_wait)
        
        # Thêm delay ngẫu nhiên
        delay = random.uniform(0, max_delay - min_delay)
        time.sleep(delay)
        
        # Thỉnh thoảng thêm delay dài (10% khả năng)
        if random.random() < 0.1:
            long_delay = random.uniform(1,3)
            self.log_message(f"Tạm dừng dài {long_delay:.1f}s để mô phỏng hành vi người dùng thực")
            time.sleep(long_delay)
        
        self.last_search_time = time.time()
    
    def simulate_human_behavior(self):
        """
        Phiên bản đơn giản, an toàn:
        - Không dùng ActionChains / move_to_element_with_offset (ngăn lỗi out-of-bounds).
        - Thực hiện scroll nhẹ + pause ngẫu nhiên.
        - 10-25% khả năng click 1 phần tử hiển thị (được kiểm tra bounding box).
        - Bọc try/except kỹ để không làm crash luồng chính.
        """
        try:
            # đảm bảo body có focus (không cần di chuyển chuột)
            try:
                self.driver.execute_script("document.body.focus();")
            except Exception:
                pass

            # Lấy kích thước viewport an toàn
            try:
                vp = self.driver.execute_script("return {w: window.innerWidth, h: window.innerHeight};")
                viewport_w = max(200, int(vp.get("w", 1200)))
                viewport_h = max(200, int(vp.get("h", 800)))
            except Exception:
                viewport_w, viewport_h = 1200, 800

            # Thực hiện 1-3 lần cuộn nhẹ (giống người đọc)
            for _ in range(random.randint(1, 3)):
                scroll_amount = random.randint(80, 350)
                try:
                    self.driver.execute_script(
                        "window.scrollBy({top: arguments[0], left: 0, behavior: 'smooth'});",
                        scroll_amount
                    )
                except Exception:
                    # fallback: instant scroll
                    try:
                        self.driver.execute_script("window.scrollBy(0, arguments[0]);", scroll_amount)
                    except Exception:
                        pass
                time.sleep(random.uniform(0.35, 1.0))

            # Thỉnh thoảng dừng lâu hơn để mô phỏng đọc
            if random.random() < 0.15:
                time.sleep(random.uniform(0.8, 2.0))

            # Có tỉ lệ nhỏ để click 1 phần tử hiển thị (an toàn)
            if random.random() < 0.2:
                try:
                    prev_url = self.driver.current_url
                except Exception:
                    prev_url = None

                candidates = []
                try:
                    elems = self.driver.find_elements(
                        By.CSS_SELECTOR,
                        "a, button, [role='button'], input[type='button'], input[type='submit']"
                    )
                    for el in elems:
                        try:
                            if not el.is_displayed():
                                continue
                            # Lấy bounding rect để đảm bảo element nằm trong viewport
                            rect = self.driver.execute_script(
                                "var r = arguments[0].getBoundingClientRect();"
                                "return {top: r.top, left: r.left, bottom: r.bottom, right: r.right, w: r.width, h: r.height};",
                                el
                            )
                            if not rect:
                                continue
                            if rect.get("w", 0) < 8 or rect.get("h", 0) < 8:
                                continue
                            # nằm (một phần) trong viewport theo trục Y
                            if rect["bottom"] >= 0 and rect["top"] < viewport_h:
                                candidates.append(el)
                        except Exception:
                            # bỏ element gây lỗi
                            continue
                except Exception:
                    candidates = []

                if candidates:
                    el = random.choice(candidates)
                    try:
                        # Click bằng selenium (an toàn hơn so với simulate mouse)
                        el.click()
                        self.log_message("Đã click ngẫu nhiên vào phần tử hiển thị")
                        time.sleep(random.uniform(0.7, 1.6))

                        # Nếu click dẫn ra trang khác, quay lại
                        try:
                            cur = self.driver.current_url
                            if prev_url and cur != prev_url:
                                time.sleep(random.uniform(0.4, 0.9))
                                try:
                                    self.driver.back()
                                    time.sleep(random.uniform(0.6, 1.2))
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    except Exception as e:
                        self.log_message(f"Click ngẫu nhiên thất bại: {e}")

            # Kết thúc với pause ngắn
            time.sleep(random.uniform(0.15, 0.6))

        except Exception as e:
            # Không để lỗi mô phỏng phá vỡ luồng chính
            self.log_message(f"Lỗi khi mô phỏng hành vi (đã bỏ qua): {e}")


    
    def is_limited(self):
        """Kiểm tra xem có thông báo giới hạn tìm kiếm không - Phiên bản cập nhật"""
        try:
            # Kiểm tra thông báo cụ thể từ hình ảnh
            specific_indicators = [
                "Bạn đã tìm kiếm quá số lần cho phép. Vui lòng thử lại sau.",
                "Bạn đã tìm kiếm quá số lần cho phép",
                "quá số lần cho phép",
                "Vui lòng thử lại sau"
            ]
            
            # Kiểm tra bằng XPath cho text cụ thể
            try:
                limit_elements = self.driver.find_elements(
                    By.XPATH, 
                    "//*[contains(text(), 'Bạn đã tìm kiếm quá số lần cho phép') or contains(text(), 'Vui lòng thử lại sau')]"
                )
                if limit_elements:
                    for element in limit_elements:
                        if element.is_displayed():
                            return True
            except:
                pass
            
            # Kiểm tra toàn bộ page text
            page_text = self.driver.page_source
            page_lower = page_text.lower()
            
            # Kiểm tra các indicator cụ thể
            if any(indicator in page_text for indicator in specific_indicators):
                return True
                
            # Kiểm tra các class hoặc ID đặc biệt có thể chứa thông báo lỗi
            error_selectors = [
                '.error-message',
                '.limit-message',
                '.zl-toast-message',
                '.toast-message',
                '[class*="error"]',
                '[class*="limit"]',
                '[class*="toast"]',
                '.text-red',  # Text màu đỏ thường là thông báo lỗi
                '.text-error'
            ]
            
            for selector in error_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed():
                            element_text = element.text
                            if any(indicator in element_text for indicator in specific_indicators):
                                return True
                except:
                    continue
                    
            return False
            
        except Exception as e:
            self.log_message(f"Lỗi khi kiểm tra giới hạn: {e}")
            return False

    def handle_search_limit(self):
        """Xử lý khi bị giới hạn tìm kiếm - Phiên bản cập nhật"""
        try:
            self.log_message("ĐÃ PHÁT HIỆN: 'Bạn đã tìm kiếm quá số lần cho phép. Vui lòng thử lại sau'")
            
            # Chụp ảnh màn hình để debug (tùy chọn)
            try:
                self.driver.save_screenshot(f"limit_detected_{int(time.time())}.png")
                self.log_message("Đã chụp ảnh màn hình lỗi")
            except:
                pass
            
            # Tăng biến đếm số lần bị giới hạn
            self.limit_count += 1
            self.log_message(f"Lần bị giới hạn thứ: {self.limit_count}")
            
            # Strategy 1: Thử đóng thông báo nếu có
            close_buttons = self.driver.find_elements(
                By.XPATH, 
                "//button[contains(text(), 'Hủy') or contains(text(), 'Đóng') or contains(text(), 'OK')]"
            )
            
            for button in close_buttons:
                try:
                    if button.is_displayed():
                        button.click()
                        self.log_message("Đã đóng thông báo bằng nút Hủy/Đóng")
                        time.sleep(2)
                        break
                except:
                    continue
            
            # Strategy 2: Xoay proxy nếu đang sử dụng
            if self.use_proxy and self.proxy_list and self.limit_count % 2 == 0:
                if self.rotate_proxy():
                    self.log_message("Đã xoay proxy để bypass giới hạn")
                    time.sleep(3)
                    # Kiểm tra lại xem còn bị giới hạn không
                    if not self.is_limited():
                        self.limit_count = 0
                        return True
            
            # Strategy 3: Chờ đợi với thời gian tăng dần
            wait_times = {
                1: (30, 60),      # Lần đầu: 30-60 giây
                2: (120, 180),    # Lần 2: 2-3 phút
                3: (300, 420),    # Lần 3: 5-7 phút
                4: (600, 900)     # Lần 4+: 10-15 phút
            }
            
            # Chọn thời gian chờ dựa trên số lần bị giới hạn
            wait_range = wait_times.get(min(self.limit_count, 4), (600, 900))
            wait_time = random.randint(wait_range[0], wait_range[1])
            
            self.log_message(f"Chờ {wait_time} giây ({wait_time//60} phút) trước khi thử lại...")
            
            # Hiển thị đồng hồ đếm ngược
            for remaining in range(wait_time, 0, -30):
                mins = remaining // 60
                secs = remaining % 60
                if mins > 0:
                    self.log_message(f"⏰ Còn lại: {mins} phút {secs} giây...")
                else:
                    self.log_message(f"⏰ Còn lại: {secs} giây...")
                time.sleep(30 if remaining > 30 else remaining)
            
            # Strategy 4: Làm mới trình duyệt theo nhiều cách
            refresh_methods = [
                lambda: self.driver.refresh(),
                lambda: self.driver.execute_script("location.reload(true);"),
                lambda: self.driver.get("https://chat.zalo.me/"),
                lambda: self.driver.get(self.driver.current_url)
            ]
            
            method = random.choice(refresh_methods)
            method()
            time.sleep(3)
            
            # Strategy 5: Clear cookies và cache nếu vẫn bị giới hạn
            if self.is_limited() and self.limit_count >= 3:
                try:
                    self.log_message("Đang xóa cookies và cache...")
                    self.driver.delete_all_cookies()
                    self.driver.execute_script("window.localStorage.clear();")
                    self.driver.execute_script("window.sessionStorage.clear();")
                    time.sleep(2)
                    self.driver.refresh()
                    time.sleep(3)
                except:
                    pass
            
            # Kiểm tra kết quả cuối cùng
            if not self.is_limited():
                self.log_message("✅ Đã bypass thành công giới hạn tìm kiếm!")
                return True
            else:
                self.log_message("❌ Vẫn bị giới hạn sau khi xử lý")
                return False
                
        except Exception as e:
            self.log_message(f"Lỗi khi xử lý giới hạn: {e}")
            return False    
    
    def check_phone_number_direct_url(self, phone: str) -> Dict:
        """Sử dụng URL trực tiếp để kiểm tra số điện thoại với rate limiting được cải thiện"""
        try:
            # Kiểm tra xem có bị giới hạn không trước khi tìm kiếm
            if self.is_limited():
                self.log_message("Phát hiện giới hạn tìm kiếm, đang xử lý...")
                if not self.handle_search_limit():
                    return {"phone": phone, "status": "Limited", "name": "Search limit exceeded"}
            
            # Tính toán thời gian chờ dựa trên số lần đã tìm kiếm
            # search_interval = self.calculate_search_interval()
            search_interval = 2
            time_since_last_search = time.time() - self.last_search_time
            
            if time_since_last_search < search_interval:
                wait_time = search_interval - time_since_last_search
                self.log_message(f"Chờ {wait_time:.1f}s để duy trì khoảng cách tìm kiếm an toàn")
                time.sleep(wait_time)
            
            self.log_message(f"Đang kiểm tra số: {phone}")
            self.search_count += 1
            
            # Sử dụng URL trực tiếp
            search_url = f"https://chat.zalo.me/?phone={phone}"
            self.driver.get(search_url)
            
            # Chờ trang load với timeout
            try:
                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            except TimeoutException:
                self.log_message("Timeout khi tải trang, thử lại...")
                self.driver.refresh()
            
            time.sleep(2)  # Thêm thời gian chờ để trang load hoàn toàn
            
            # Kiểm tra kết quả
            result = self.check_search_result_direct(phone)
            
            # Thêm delay ngẫu nhiên giống người dùng thực
            self.human_like_delay(min_delay=1, max_delay=3)
            # self.simulate_human_behavior()
            
            return result
            
        except Exception as e:
            self.log_message(f"Lỗi khi kiểm tra {phone}: {e}")
            return {"phone": phone, "status": "Error", "name": str(e)}
    
    # def calculate_search_interval(self) -> float:
    #     """
    #     Khoảng thời gian giữa các lần tìm kiếm.
    #     - Ban đầu nhanh (3–5 giây).
    #     - Sau 50 số: tăng nhẹ (5–7 giây).
    #     - Sau 100 số: tăng hơn chút (7–10 giây).
    #     """
    #     if self.search_count > 100:
    #         return random.uniform(7.0, 10.0)
    #     elif self.search_count > 50:
    #         return random.uniform(5.0, 7.0)
    #     else:
    #         return random.uniform(3.0, 5.0)

    
    def check_search_result_direct(self, phone: str) -> Dict:
        """Kiểm tra kết quả tìm kiếm từ URL trực tiếp với cải tiến"""
        try:
            # Kiểm tra xem modal thông tin tài khoản có xuất hiện không
            modal_selectors = [
                '.zl-modal__dialog',
                '.account-info-modal',
                '.pi-mini-info-section',
                '[role="dialog"]',
                '.profile-dialog',
                '.user-info-popup'
            ]
            
            modal_visible = False
            for selector in modal_selectors:
                try:
                    modal_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in modal_elements:
                        if element.is_displayed():
                            modal_visible = True
                            break
                    if modal_visible:
                        break
                except:
                    continue
            
            if modal_visible:
                # Tìm tên trong modal
                name = self.extract_name_from_modal()
                
                if not name:
                    name = "Người dùng Zalo"
                
                self.log_message(f"Đã tìm thấy Zalo - Tên: {name}")
                return {"phone": phone, "status": "Có Zalo", "name": name}
            
            # Kiểm tra xem có thông báo lỗi không
            error_indicators = [
                "không tồn tại",
                "số điện thoại chưa",
                "not found",
                "không tìm thấy",
                "chưa đăng ký",
                "invalid phone"
            ]
            
            page_text = self.driver.page_source.lower()
            if any(indicator in page_text for indicator in error_indicators):
                self.log_message("Số điện thoại không có Zalo")
                return {"phone": phone, "status": "Không có Zalo", "name": ""}
            
            # Kiểm tra nút "Nhắn tin" - dấu hiệu có Zalo
            try:
                message_buttons = self.driver.find_elements(
                    By.XPATH, 
                    "//button[contains(., 'Nhắn tin') or contains(., 'Chat') or contains(., 'Message')]"
                )
                if message_buttons:
                    for button in message_buttons:
                        if button.is_displayed():
                            name = self.extract_name_from_page()
                            self.log_message(f"Đã tìm thấy Zalo (qua nút nhắn tin) - Tên: {name}")
                            return {"phone": phone, "status": "Có Zalo", "name": name}
            except:
                pass
            
            # Kiểm tra avatar hoặc ảnh đại diện
            try:
                avatar_elements = self.driver.find_elements(By.CSS_SELECTOR, "img[src*='avatar'], img[alt*='avatar'], .avatar, .user-avatar")
                if avatar_elements and any(el.is_displayed() for el in avatar_elements):
                    name = self.extract_name_from_page()
                    if name:
                        self.log_message(f"Đã tìm thấy Zalo (qua avatar) - Tên: {name}")
                        return {"phone": phone, "status": "Có Zalo", "name": name}
            except:
                pass
            
            # Mặc định là không có Zalo nếu không tìm thấy dấu hiệu nào
            self.log_message("Số điện thoại không có Zalo (mặc định)")
            return {"phone": phone, "status": "Không có Zalo", "name": ""}
            
        except Exception as e:
            self.log_message(f"Lỗi khi kiểm tra kết quả: {e}")
            return {"phone": phone, "status": "Error", "name": str(e)}
    
    def extract_name_from_modal(self) -> str:
        """Trích xuất tên từ modal thông tin"""
        try:
            name_selectors = [
                '.pi-mini-info-section__name',
                '.account-name',
                '.user-name',
                '.profile-name',
                '[class*="name"]',
                'h1',
                'h2',
                'h3',
                '.title',
                '.display-name'
            ]
            
            for selector in name_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed():
                            text = element.get_attribute("textContent") or element.text
                            if text and len(text.strip()) > 1 and len(text.strip()) < 50:
                                return text.strip()
                except:
                    continue
            
            return ""
        except:
            return ""
    
    def extract_name_from_page(self) -> str:
        """Cố gắng trích xuất tên từ trang với nhiều phương pháp hơn"""
        try:
            # Thử lấy tên từ thẻ title
            title = self.driver.title
            if title and "Zalo" not in title and len(title) > 3 and len(title) < 30:
                return title
            
            # Các selector có thể chứa tên
            name_selectors = [
                'h1', 'h2', 'h3',
                '.name', '.username', '.profile-name',
                '[class*="title"]', '[class*="name"]',
                '.display-name', '.user-display-name',
                'title', 'meta[property="og:title"]'
            ]
            
            for selector in name_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed() or selector == 'meta[property="og:title"]':
                            text = element.get_attribute("textContent") or element.text or element.get_attribute("content")
                            if text and len(text.strip()) > 1 and len(text.strip()) < 50:
                                return text.strip()
                except:
                    continue
            
            return "Người dùng Zalo"
        except:
            return "Người dùng Zalo"
    
    def login(self) -> bool:
        """Chờ người dùng đăng nhập thủ công với cải tiến"""
        try:
            self.driver.get("https://chat.zalo.me/")
            self.log_message("Đang chờ đăng nhập...")
            
            # Chờ cho đến khi có dấu hiệu đã đăng nhập
            try:
                # Chờ tối đa 120 giây để đăng nhập
                login_wait = WebDriverWait(self.driver, 120)
                login_wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-id*='btn_'], .conversation-list, .chat-list"))
                )
                self.log_message("Đăng nhập thành công!")
                
                # Chờ thêm một chút để đảm bảo trang đã load hoàn toàn
                time.sleep(3)
                return True
            except TimeoutException:
                self.log_message("Timeout khi chờ đăng nhập")
                return False
                
        except Exception as e:
            self.log_message(f"Lỗi khi đăng nhập: {e}")
            return False
    
    def process_numbers(self, phone_numbers: List[str], batch_size: int = 10) -> List[Dict]:
        """Xử lý danh sách số điện thoại theo batch với khoảng cách lớn hơn giữa các batch"""
        results = []
        total_numbers = len(phone_numbers)
        
        for i, phone in enumerate(phone_numbers, 1):
            try:
                # Đảm bảo số điện thoại có định dạng đúng
                phone_str = str(phone).strip().replace(" ", "").replace("-", "").replace("+84", "0")
                if len(phone_str) == 9 and not phone_str.startswith('0'):
                    phone_str = '0' + phone_str
                
                # Kiểm tra định dạng số điện thoại
                if not phone_str.isdigit() or len(phone_str) != 10:
                    self.log_message(f"Số {phone_str} không hợp lệ, bỏ qua")
                    results.append({"phone": phone_str, "status": "Invalid", "name": ""})
                    continue
                
                # Sử dụng phương pháp URL trực tiếp
                result = self.check_phone_number_direct_url(phone_str)
                results.append(result)
                
                # Lưu tạm sau mỗi batch
                if i % batch_size == 0:
                    batch_num = i // batch_size
                    self.save_results(results, f"zalo_results_batch_{batch_num}.csv")
                    self.log_message(f"Đã xử lý {i}/{total_numbers} số")
                    
                    # Nghỉ ngơi giữa các batch
                    if i < total_numbers:
                        batch_break = random.randint(30, 120)
                        self.log_message(f"Nghỉ {batch_break} giây giữa các batch...")
                        time.sleep(batch_break)
                    
            except Exception as e:
                self.log_message(f"Lỗi nghiêm trọng với số {phone}: {e}")
                results.append({"phone": phone, "status": "Fatal Error", "name": str(e)})
        
        return results
    
    def save_results(self, results: List[Dict], filename: str = "zalo_results.csv"):
        """Lưu kết quả ra file với định dạng được cải thiện"""
        try:
            df = pd.DataFrame(results)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            self.log_message(f"Đã lưu kết quả vào {filename}")
            
            # Lưu thêm file JSON để dễ xử lý sau này
            json_filename = filename.replace('.csv', '.json')
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.log_message(f"Lỗi khi lưu file: {e}")
    
    def close(self):
        """Đóng trình duyệt"""
        try:
            self.driver.quit()
            self.log_message("Đã đóng trình duyệt")
        except:
            pass

# Hàm tiện ích để lấy proxy tự động
def get_free_proxies(count: int = 5) -> List[str]:
    """Lấy danh sách proxy miễn phí"""
    proxies = []
    try:
        proxy = FreeProxy(rand=True, timeout=1).get()
        if proxy:
            proxies.append(proxy)
    except:
        pass
        
    # Fallback: một số proxy mẫu (nên thay thế bằng proxy thực)
    if not proxies:
        proxies = [
            "http://103.145.128.18:8080",
            "http://103.175.237.9:3128",
            "http://103.155.54.26:83",
            "http://103.148.178.228:80",
            "http://103.159.90.14:83"
        ]
    
    return proxies[:count]

def main():
    # Đọc danh sách số điện thoại
    try:
        df = pd.read_csv("numbers.csv")
        phone_numbers = df['phone'].astype(str).str.strip().tolist()
        logger.info(f"Đã đọc {len(phone_numbers)} số từ file")
    except Exception as e:
        logger.error(f"Lỗi khi đọc file: {e}")
        return
    
    proxies = get_free_proxies(3)
        # Khởi tạo checker
    checker = ZaloChecker(
            headless=False, 
            use_proxy=True, 
            proxy_list=proxies
        )    
    try:
        # Đăng nhập
        if not checker.login():
            input("👉 Vui lòng đăng nhập thủ công rồi nhấn Enter để tiếp tục...")
        
        # Xử lý số điện thoại
        start_time = time.time()
        results = checker.process_numbers(phone_numbers)
        
        # Lưu kết quả cuối cùng
        checker.save_results(results, "zalo_results_final.csv")
        
        # Thống kê chi tiết
        end_time = time.time()
        total_time = end_time - start_time
        stats = pd.DataFrame(results)['status'].value_counts()
        
        logger.info(f"\n=== HOÀN TẤT ===")
        logger.info(f"Thời gian: {total_time:.1f} giây")
        logger.info(f"Tốc độ: {len(phone_numbers)/total_time*60:.1f} số/phút")
        logger.info(f"Thống kê:")
        for status, count in stats.items():
            percentage = count / len(results) * 100
            logger.info(f"  {status}: {count} ({percentage:.1f}%)")
        
    except KeyboardInterrupt:
        logger.info("Đã dừng bởi người dùng")
    except Exception as e:
        logger.error(f"Lỗi không mong muốn: {e}")
    finally:
        checker.close()

if __name__ == "__main__":
    main()