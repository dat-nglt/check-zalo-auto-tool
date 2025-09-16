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
    
    def random_delay(self, min_time: float = 0.5, max_time: float = 1.5) -> None:
        """Tạo delay ngẫu nhiên ngắn"""
        delay = random.uniform(min_time, max_time)
        time.sleep(delay)
    
    def js_click(self, selector: str) -> bool:
        """Click element bằng JavaScript để tránh bị intercepted"""
        try:
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            self.driver.execute_script("arguments[0].click();", element)
            return True
        except:
            return False
    
    def close_modal(self):
        """Đóng modal thông tin tài khoản bằng nút close"""
        try:
            # Đóng modal bằng nút close chính xác
            close_selectors = [
                'div[icon="close f16"]',
                '[aria-label="Close"]',
                '.zl-modal__close',
                '.modal-close',
                '[data-dismiss="modal"]'
            ]
            
            for selector in close_selectors:
                try:
                    close_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for btn in close_buttons:
                        if btn.is_displayed():
                            self.driver.execute_script("arguments[0].click();", btn)
                            self.random_delay(0.3, 0.7)
                            logger.info("Đã đóng modal thông tin tài khoản")
                            return True
                except:
                    continue
            
            # Nếu không tìm thấy nút close, thử click ra ngoài
            try:
                overlay = self.driver.find_element(By.CSS_SELECTOR, '.zl-modal__container')
                self.driver.execute_script("arguments[0].click();", overlay)
                self.random_delay(0.3, 0.7)
                logger.info("Đã click ra ngoài để đóng modal")
                return True
            except:
                pass
                
            return False
        except Exception as e:
            logger.warning(f"Lỗi khi đóng modal: {e}")
            return False
    
    def check_phone_number(self, phone: str) -> Dict:
        """Kiểm tra một số điện thoại - phiên bản tối ưu với modal"""
        try:
            logger.info(f"Đang kiểm tra số: {phone}")
            
            # 1. Click nút Thêm bạn bằng JS
            if not self.js_click("[data-id='btn_Main_AddFrd']"):
                return {"phone": phone, "status": "Error", "name": "Cannot click add friend"}
            
            self.random_delay(0.5, 1.0)
            
            # 2. Nhập số điện thoại
            try:
                phone_input = self.wait.until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-id='txt_Main_AddFrd_Phone']"))
                )
                phone_input.clear()
                phone_input.send_keys(str(phone))
            except:
                return {"phone": phone, "status": "Error", "name": "Cannot find phone input"}
            
            self.random_delay(0.3, 0.7)
            
            # 3. Click nút Tìm kiếm bằng JS
            if not self.js_click("[data-id='btn_Main_AddFrd_Search']"):
                return {"phone": phone, "status": "Error", "name": "Cannot click search"}
            
            # 4. Chờ kết quả - KIỂM TRA MODAL THÔNG TIN TÀI KHOẢN
            result = None
            modal_appeared = False
            
            # Chờ tối đa 5 giây để modal xuất hiện
            for _ in range(10):
                try:
                    # Kiểm tra modal thông tin tài khoản có xuất hiện không
                    modal_elements = self.driver.find_elements(
                        By.CSS_SELECTOR, '.zl-modal__dialog, [class*="modal"], [title*="Thông tin tài khoản"]'
                    )
                    
                    if modal_elements and any(el.is_displayed() for el in modal_elements):
                        modal_appeared = True
                        logger.info("Modal thông tin tài khoản đã xuất hiện - Số CÓ Zalo")
                        
                        # Lấy thông tin từ modal
                        result = self.extract_info_from_modal(phone)
                        break
                    
                    # Kiểm tra thông báo lỗi
                    error_elements = self.driver.find_elements(
                        By.CSS_SELECTOR, '.error-message, .no-result, [class*="error"]'
                    )
                    if error_elements and any('không tồn tại' in el.text for el in error_elements if el.is_displayed()):
                        logger.info("Thông báo lỗi xuất hiện - Số KHÔNG có Zalo")
                        result = {"phone": phone, "status": "Không có Zalo", "name": ""}
                        break
                        
                except:
                    pass
                
                time.sleep(0.5)
            
            # Nếu không phát hiện modal sau 5 giây, coi như không có Zalo
            if result is None:
                if not modal_appeared:
                    logger.info("Không thấy modal thông tin - Số KHÔNG có Zalo")
                    result = {"phone": phone, "status": "Không có Zalo", "name": ""}
                else:
                    result = {"phone": phone, "status": "Unknown", "name": "Cần kiểm tra thủ công"}
            
            logger.info(f"Kết quả: {phone} - {result['status']}")
            return result
            
        except Exception as e:
            logger.error(f"Lỗi khi kiểm tra {phone}: {e}")
            return {"phone": phone, "status": "Error", "name": str(e)}
        finally:
            # 5. ĐÓNG MODAL THAY VÌ RELOAD TRANG
            self.close_modal()
            self.random_delay(0.5, 1.0)
    
    def extract_info_from_modal(self, phone: str) -> Dict:
        """Trích xuất thông tin từ modal thông tin tài khoản"""
        try:
            # Tìm tên trong modal
            name_selectors = [
                '.pi-mini-info-section__name',
                '.truncate[title]',
                '[class*="name"]',
                '[class*="title"]'
            ]
            
            name = ""
            for selector in name_selectors:
                try:
                    name_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in name_elements:
                        if element.is_displayed():
                            name_text = element.get_attribute("title") or element.text or element.get_attribute("textContent")
                            if name_text and name_text.strip() and len(name_text.strip()) > 1:
                                name = name_text.strip()
                                break
                    if name:
                        break
                except:
                    continue
            
            # Nếu không tìm thấy tên, đặt tên mặc định
            if not name:
                name = "Người dùng Zalo"
            
            return {"phone": phone, "status": "Có Zalo", "name": name}
            
        except Exception as e:
            logger.warning(f"Lỗi khi trích xuất thông tin từ modal: {e}")
            return {"phone": phone, "status": "Có Zalo", "name": "Người dùng Zalo"}
    
    def process_numbers(self, phone_numbers: List[str], batch_size: int = 20) -> List[Dict]:
        """Xử lý danh sách số điện thoại theo batch"""
        results = []
        
        for i, phone in enumerate(phone_numbers, 1):
            try:
                # Đảm bảo số điện thoại có định dạng đúng
                phone_str = str(phone).strip()
                if len(phone_str) == 9 and not phone_str.startswith('0'):
                    phone_str = '0' + phone_str
                
                result = self.check_phone_number(phone_str)
                results.append(result)
                
                # Lưu tạm sau mỗi batch
                if i % batch_size == 0:
                    self.save_results(results, f"zalo_results_batch_{i//batch_size}.csv")
                    logger.info(f"Đã xử lý {i}/{len(phone_numbers)} số")
                    
                # Nghỉ ngơi ngẫu nhiên sau mỗi 10-20 số
                if i % random.randint(10, 20) == 0:
                    rest_time = random.randint(10, 20)
                    logger.info(f"Nghỉ {rest_time} giây...")
                    time.sleep(rest_time)
                    
            except Exception as e:
                logger.error(f"Lỗi nghiêm trọng với số {phone}: {e}")
                results.append({"phone": phone, "status": "Fatal Error", "name": str(e)})
        
        return results
    
    def save_results(self, results: List[Dict], filename: str = "zalo_results.csv"):
        """Lưu kết quả ra file"""
        try:
            df = pd.DataFrame(results)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            logger.info(f"Đã lưu kết quả vào {filename}")
        except Exception as e:
            logger.error(f"Lỗi khi lưu file: {e}")
    
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