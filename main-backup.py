from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
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
        """Tìm và click element với xử lý lỗi"""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            element.click()
            self.random_delay(0.5, 1.5)
            return True
        except Exception as e:
            logger.warning(f"Không thể click {selector}: {e}")
            return False
    
    def check_phone_number(self, phone: str) -> Dict:
        """Kiểm tra một số điện thoại"""
        try:
            logger.info(f"Đang kiểm tra số: {phone}")
            
            # 1. Click nút Thêm bạn
            if not self.find_and_click("[data-id='btn_Main_AddFrd']"):
                return {"phone": phone, "status": "Error", "name": "Cannot click add friend"}
            
            # 2. Nhập số điện thoại (NHẬP MỘT LẦN THAY VÌ TỪNG KÝ TỰ)
            phone_input = self.wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-id='txt_Main_AddFrd_Phone']"))
            )
            phone_input.clear()
            self.random_delay(0.2, 0.5)
            
            # NHẬP TOÀN BỘ SỐ ĐIỆN THOẠI MỘT LẦN
            phone_input.send_keys(str(phone))
            self.random_delay(0.5, 1.0)  # Delay ngắn sau khi nhập
            
            # 3. Click nút Tìm kiếm
            if not self.find_and_click("[data-id='btn_Main_AddFrd_Search']"):
                return {"phone": phone, "status": "Error", "name": "Cannot click search"}
            
            # 4. Chờ kết quả và phân tích
            self.random_delay(2, 4)
            
            # Kiểm tra multiple cases
            result = self.analyze_result(phone)
            logger.info(f"Kết quả: {phone} - {result['status']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Lỗi khi kiểm tra {phone}: {e}")
            return {"phone": phone, "status": "Error", "name": str(e)}
        finally:
            # 5. Reset trạng thái (nếu cần)
            self.try_reset_state()
    
    def analyze_result(self, phone: str) -> Dict:
        """Phân tích kết quả tìm kiếm với nhiều trường hợp"""
        try:
            # Case 1: Tìm thấy người dùng
            name_elements = self.driver.find_elements(
                By.CSS_SELECTOR, ".flx.rel.flx-al-c .truncate, .search-result-item .name"
            )
            
            if name_elements:
                name = name_elements[0].get_attribute("title") or name_elements[0].text
                return {"phone": phone, "status": "Có Zalo", "name": name.strip()}
            
            # Case 2: Không tìm thấy
            error_elements = self.driver.find_elements(
                By.CSS_SELECTOR, ".error-message, .no-result, [class*='error']"
            )
            
            if error_elements or "không tồn tại" in self.driver.page_source.lower():
                return {"phone": phone, "status": "Không có Zalo", "name": ""}
            
            # Case 3: Cần thêm thông tin (avatar mặc định, v.v.)
            avatar_elements = self.driver.find_elements(
                By.CSS_SELECTOR, "img[src*='default']"
            )
            
            if avatar_elements:
                return {"phone": phone, "status": "Có Zalo", "name": "Người dùng ẩn danh"}
            
            # Mặc định: không tìm thấy
            return {"phone": phone, "status": "Không có Zalo", "name": ""}
            
        except Exception as e:
            return {"phone": phone, "status": "Error", "name": f"Analysis error: {str(e)}"}
    
    def try_reset_state(self):
        """Cố gắng reset trạng thái về ban đầu"""
        try:
            # Thử click ra ngoài hoặc nút back
            self.driver.execute_script("window.history.go(-1)")
            self.random_delay()
        except:
            try:
                # Alternative: reload page
                self.driver.get("https://chat.zalo.me/")
                self.random_delay(2, 3)
            except:
                pass
    
    def process_numbers(self, phone_numbers: List[str], batch_size: int = 10) -> List[Dict]:
        """Xử lý danh sách số điện thoại theo batch"""
        results = []
        
        for i, phone in enumerate(phone_numbers, 1):
            try:
                result = self.check_phone_number(phone)
                results.append(result)
                
                # Lưu tạm sau mỗi batch
                if i % batch_size == 0:
                    self.save_results(results, f"zalo_results_batch_{i//batch_size}.csv")
                    logger.info(f"Đã xử lý {i}/{len(phone_numbers)} số")
                    
                # Nghỉ ngơi sau mỗi 20 số
                if i % 20 == 0:
                    rest_time = random.randint(30, 60)
                    logger.info(f"Nghỉ {rest_time} giây...")
                    time.sleep(rest_time)
                    
            except Exception as e:
                logger.error(f"Lỗi nghiêm trọng với số {phone}: {e}")
                results.append({"phone": phone, "status": "Fatal Error", "name": str(e)})
                
                # Thử khởi động lại trình duyệt nếu lỗi nghiêm trọng
                if "session" in str(e).lower() or "browser" in str(e).lower():
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
        except:
            pass
        
        time.sleep(5)
        self.__init__()
        self.login()
    
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
        phone_numbers = df['phone'].astype(str).tolist()
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
        results = checker.process_numbers(phone_numbers)
        
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