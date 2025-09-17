import random


def advanced_evasion_techniques(self):
    """Kỹ thuật tránh phát hiện nâng cao"""
    try:
        # Xóa cookies và storage định kỳ
        if random.random() < 0.2:  # 20% khả năng
            self.driver.delete_all_cookies()
            self.driver.execute_script("window.localStorage.clear();")
            self.driver.execute_script("window.sessionStorage.clear();")
            self.log_message("Đã xóa cookies và storage")
        
        # Thay đổi User-Agent định kỳ
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15"
        ]
        
        if random.random() < 0.1:  # 10% khả năng
            new_ua = random.choice(user_agents)
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": new_ua})
            self.log_message(f"Đã thay đổi User-Agent: {new_ua[:50]}...")
        
        # Thay đổi kích thước màn hình
        if random.random() < 0.15:  # 15% khả năng
            width = random.randint(1200, 1920)
            height = random.randint(800, 1080)
            self.driver.set_window_size(width, height)
            self.log_message(f"Đã thay đổi kích thước cửa sổ: {width}x{height}")
            
    except Exception as e:
        self.log_message(f"Lỗi kỹ thuật tránh phát hiện: {e}")