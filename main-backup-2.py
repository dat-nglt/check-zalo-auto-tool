from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException
import pandas as pd
import time
import random
import logging
from typing import List, Dict, Optional
import json

# --- Cấu hình logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('zalo_checker.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ZaloChecker:
    def __init__(self, headless: bool = False):
        """Khởi tạo trình duyệt với các tùy chọn"""
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--start-maximized')  # Thêm để tránh responsive issues
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        self.wait = WebDriverWait(self.driver, 15)
        self.results: List[Dict] = []
        
    def login(self) -> bool:
        """Chờ người dùng đăng nhập thủ công"""
        try:
            self.driver.get("https://chat.zalo.me/")
            logger.info("Đang chờ đăng nhập...")
            
            # Chờ cho đến khi có dấu hiệu đã đăng nhập
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-id*='btn_']"))
                )
                logger.info("Đăng nhập thành công!")
                return True
            except TimeoutException:
                logger.warning("Có vẻ như chưa đăng nhập thành công")
                return False
                
        except Exception as e:
            logger.error(f"Lỗi khi đăng nhập: {e}")
            return False
    
    def random_delay(self, min_time: float = 1.0, max_time: float = 3.0) -> None:
        """Tạo delay ngẫu nhiên để tránh bị phát hiện"""
        delay = random.uniform(min_time, max_time)
        time.sleep(delay)
    
    def find_and_click(self, selector: str, timeout: int = 10) -> bool:
        """Tìm và click element với xử lý lỗi, bao gồm click intercepted"""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            
            # Thử click bằng JavaScript nếu bị intercepted
            try:
                element.click()
            except ElementClickInterceptedException:
                logger.warning(f"Click bị intercepted, thử click bằng JavaScript: {selector}")
                self.driver.execute_script("arguments[0].click();", element)
            
            self.random_delay(0.5, 1.5)
            return True
            
        except Exception as e:
            logger.warning(f"Không thể click {selector}: {e}")
            return False
    
    def close_modals_if_any(self):
        """Đóng các modal/popup nếu có"""
        try:
            # Thử tìm và đóng các modal thường gặp trên Zalo
            modal_selectors = [
                ".zl-modal__close",
                "[aria-label='Close']",
                ".btn-close",
                ".modal-close",
                "[data-id*='close']",
                "[data-id*='btn_Dialog']"
            ]
            
            for selector in modal_selectors:
                try:
                    close_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for btn in close_buttons:
                        if btn.is_displayed():
                            self.driver.execute_script("arguments[0].click();", btn)
                            logger.info(f"Đã đóng modal với selector: {selector}")
                            self.random_delay(1, 2)
                            return True
                except:
                    continue
                    
            return False
        except Exception as e:
            logger.warning(f"Lỗi khi đóng modal: {e}")
            return False
    
    def check_phone_number(self, phone: str) -> Dict:
        """Kiểm tra một số điện thoại"""
        try:
            logger.info(f"Đang kiểm tra số: {phone}")
            
            # 0. Đóng modal nếu có trước khi click
            self.close_modals_if_any()
            self.random_delay(1, 2)
            
            # 1. Click nút Thêm bạn (với retry)
            max_retries = 3
            for attempt in range(max_retries):
                if self.find_and_click("[data-id='btn_Main_AddFrd']"):
                    break
                else:
                    if attempt < max_retries - 1:
                        logger.warning(f"Thử lại click nút Thêm bạn (lần {attempt + 2})")
                        self.close_modals_if_any()
                        self.random_delay(2, 3)
                    else:
                        return {"phone": phone, "status": "Error", "name": "Cannot click add friend after retries"}
            
            # 2. Đợi form nhập số xuất hiện
            try:
                phone_input = self.wait.until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-id='txt_Main_AddFrd_Phone']"))
                )
            except TimeoutException:
                # Có thể form đã mở nhưng không tìm thấy selector chính xác
                # Thử tìm input số điện thoại bằng các selector khác
                phone_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='tel'], input[placeholder*='phone'], input[placeholder*='số điện thoại']")
                if phone_inputs:
                    phone_input = phone_inputs[0]
                else:
                    return {"phone": phone, "status": "Error", "name": "Cannot find phone input"}
            
            # 3. Nhập số điện thoại
            phone_input.clear()
            self.random_delay(0.2, 0.5)
            
            # Nhập toàn bộ số điện thoại một lần
            phone_input.send_keys(str(phone))
            self.random_delay(0.5, 1.0)
            
            # 4. Click nút Tìm kiếm
            if not self.find_and_click("[data-id='btn_Main_AddFrd_Search']"):
                # Thử các selector khác cho nút tìm kiếm
                search_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[type='submit'], button:contains('Tìm'), button:contains('Search')")
                for btn in search_buttons:
                    if btn.is_displayed():
                        self.driver.execute_script("arguments[0].click();", btn)
                        break
                else:
                    return {"phone": phone, "status": "Error", "name": "Cannot click search"}
            
            # 5. Chờ kết quả và phân tích
            self.random_delay(3, 5)  # Tăng thời gian chờ kết quả
            
            # Kiểm tra multiple cases
            result = self.analyze_result(phone)
            logger.info(f"Kết quả: {phone} - {result['status']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Lỗi khi kiểm tra {phone}: {e}")
            return {"phone": phone, "status": "Error", "name": str(e)}
        finally:
            # 6. Reset trạng thái (nếu cần)
            self.try_reset_state()
    
    def analyze_result(self, phone: str) -> Dict:
        """Phân tích kết quả tìm kiếm với nhiều trường hợp"""
        try:
            # Chờ kết quả tải xong
            self.random_delay(2, 3)
            
            # Case 1: Tìm thấy người dùng
            name_selectors = [
                ".flx.rel.flx-al-c .truncate",
                ".search-result-item .name",
                ".friend-name",
                ".user-name",
                "[data-id*='name']",
                ".title"  # Thêm selector phổ biến
            ]
            
            for selector in name_selectors:
                name_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if name_elements:
                    for element in name_elements:
                        if element.is_displayed():
                            name = element.get_attribute("title") or element.text or element.get_attribute("textContent")
                            if name and name.strip():
                                return {"phone": phone, "status": "Có Zalo", "name": name.strip()}
            
            # Case 2: Không tìm thấy - kiểm tra thông báo lỗi
            error_selectors = [
                ".error-message",
                ".no-result",
                "[class*='error']",
                "[class*='empty']",
                "[class*='not-found']",
                ".zl-empty__text"  # Selector mới cho Zalo
            ]
            
            page_text = self.driver.page_source.lower()
            error_keywords = ["không tồn tại", "không tìm thấy", "sai số điện thoại", "invalid", "not found"]
            
            for selector in error_selectors:
                error_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if error_elements:
                    return {"phone": phone, "status": "Không có Zalo", "name": ""}
            
            if any(keyword in page_text for keyword in error_keywords):
                return {"phone": phone, "status": "Không có Zalo", "name": ""}
            
            # Case 3: Kiểm tra avatar/default image
            avatar_selectors = [
                "img[src*='default']",
                "img[alt*='avatar']",
                ".avatar-image"
            ]
            
            for selector in avatar_selectors:
                avatar_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if avatar_elements:
                    return {"phone": phone, "status": "Có Zalo", "name": "Người dùng ẩn danh"}
            
            # Mặc định: không tìm thấy (sau khi đã kiểm tra nhiều trường hợp)
            return {"phone": phone, "status": "Không có Zalo", "name": ""}
            
        except Exception as e:
            return {"phone": phone, "status": "Error", "name": f"Analysis error: {str(e)}"}
    
    def try_reset_state(self):
        """Cố gắng reset trạng thái về ban đầu"""
        try:
            # Thử đóng modal trước
            self.close_modals_if_any()
            
            # Thử click ra ngoài hoặc nút back
            self.driver.execute_script("window.history.go(-1)")
            self.random_delay(1, 2)
            
            # Nếu vẫn không được, reload trang
            if "addfriend" in self.driver.current_url.lower():
                self.driver.get("https://chat.zalo.me/")
                self.random_delay(2, 3)
                
        except:
            try:
                # Fallback: reload page
                self.driver.get("https://chat.zalo.me/")
                self.random_delay(2, 3)
            except:
                pass
    
    def process_numbers(self, phone_numbers: List[str], batch_size: int = 10) -> List[Dict]:
        """Xử lý danh sách số điện thoại theo batch"""
        results = []
        
        for i, phone in enumerate(phone_numbers, 1):
            try:
                # Đảm bảo số có định dạng đúng (thêm 0 nếu cần)
                phone_str = str(phone).strip()
                if not phone_str.startswith('0') and len(phone_str) == 9:
                    phone_str = '0' + phone_str
                
                result = self.check_phone_number(phone_str)
                results.append(result)
                
                # Lưu tạm sau mỗi batch
                if i % batch_size == 0:
                    self.save_results(results, f"zalo_results_batch_{i//batch_size}.csv")
                    logger.info(f"Đã xử lý {i}/{len(phone_numbers)} số")
                    
                # Nghỉ ngơi sau mỗi 10 số (giảm từ 20 xuống)
                if i % 10 == 0:
                    rest_time = random.randint(20, 40)
                    logger.info(f"Nghỉ {rest_time} giây...")
                    time.sleep(rest_time)
                    
            except Exception as e:
                logger.error(f"Lỗi nghiêm trọng với số {phone}: {e}")
                results.append({"phone": phone, "status": "Fatal Error", "name": str(e)})
                
                # Thử khởi động lại trình duyệt nếu lỗi nghiêm trọng
                if any(keyword in str(e).lower() for keyword in ["session", "browser", "disconnected", "invalid"]):
                    self.restart_browser()
        
        return results
    
    def save_results(self, results: List[Dict], filename: str = "zalo_results.csv"):
        """Lưu kết quả ra file"""
        try:
            df = pd.DataFrame(results)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            logger.info(f"Đã lưu kết quả vào {filename}")
        except Exception as e:
            logger.error(f"Lỗi khi lưu file: {e}")
    
    def restart_browser(self):
        """Khởi động lại trình duyệt"""
        try:
            self.driver.quit()
            logger.warning("Đã khởi động lại trình duyệt do lỗi nghiêm trọng")
        except:
            pass
        
        time.sleep(5)
        self.__init__()
        if not self.login():
            input("👉 Vui lòng đăng nhập lại thủ công rồi nhấn Enter để tiếp tục...")
    
    def close(self):
        """Đóng trình duyệt"""
        try:
            self.driver.quit()
            logger.info("Đã đóng trình duyệt")
        except:
            pass

# --- Hàm main ---
def main():
    # Đọc danh sách số điện thoại
    try:
        df = pd.read_csv("numbers.csv")
        # Xử lý số điện thoại: convert sang string và làm sạch
        phone_numbers = df['phone'].astype(str).str.strip().tolist()
        logger.info(f"Đã đọc {len(phone_numbers)} số từ file")
    except Exception as e:
        logger.error(f"Lỗi khi đọc file: {e}")
        return
    
    # Khởi tạo checker
    checker = ZaloChecker(headless=False)
    
    try:
        # Đăng nhập
        if not checker.login():
            input("👉 Vui lòng đăng nhập thủ công rồi nhấn Enter để tiếp tục...")
        
        # Xử lý số điện thoại
        results = checker.process_numbers(phone_numbers, batch_size=5)  # Giảm batch size
        
        # Lưu kết quả cuối cùng
        checker.save_results(results, "zalo_results_final.csv")
        
        # Thống kê
        stats = pd.DataFrame(results)['status'].value_counts()
        logger.info(f"\n=== THỐNG KÊ ===\n{stats}")
        
    except KeyboardInterrupt:
        logger.info("Đã dừng bởi người dùng")
    except Exception as e:
        logger.error(f"Lỗi không mong muốn: {e}")
    finally:
        checker.close()

if __name__ == "__main__":
    main()