"""
Tkinter-based UI wrapper for ZaloChecker

Save this file next to your existing module (the code you gave).
Expected module filename: zalo_checker_module.py (adjust import if different).

Features:
- Load CSV with a "phone" column
- Set batch size and headless option
- Start/Stop checking (Stop attempts to close the browser)
- Shows live progress in a Treeview and a log text area
- Save results to a CSV

Run: python zalo_checker_tkinter_ui.py
"""

import threading
import queue
import os
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd

# Adjust this import to match the filename where your ZaloChecker class lives.
# If you put the provided checker code in zalo_checker_module.py, keep this.
try:
    from zalo_checker_module import ZaloChecker
except Exception:
    # fallback: maybe the user kept the code in the same file name 'zalo_checker.py'
    try:
        from zalo_checker_module import ZaloChecker
    except Exception:
        ZaloChecker = None


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Zalo Checker - GUI (Tkinter)")
        self.geometry("1000x700")
        self.minsize(900, 600)
        
        # Configure style for colored buttons
        self.style = ttk.Style()
        
        # Configure button styles with appropriate colors
        self.style.map('Primary.TButton', 
                      foreground=[('pressed', 'white'), ('active', 'white')],
                      background=[('pressed', '#0056b3'), ('active', '#0069d9')])
        self.style.map('Success.TButton', 
                      foreground=[('pressed', 'white'), ('active', 'white')],
                      background=[('pressed', '#1e7e34'), ('active', '#218838')])
        self.style.map('Danger.TButton', 
                      foreground=[('pressed', 'white'), ('active', 'white')],
                      background=[('pressed', '#c82333'), ('active', '#dc3545')])
        self.style.map('Warning.TButton', 
                      foreground=[('pressed', 'white'), ('active', 'white')],
                      background=[('pressed', '#e0a800'), ('active', '#ffc107')])
        self.style.map('Info.TButton', 
                      foreground=[('pressed', 'white'), ('active', 'white')],
                      background=[('pressed', '#138496'), ('active', '#17a2b8')])
        
        # Configure treeview style
        self.style.configure('Treeview', rowheight=25)
        self.style.configure('Treeview.Heading', font=('Arial', 10, 'bold'))

        self.checker = None
        self.worker_thread = None
        self.worker_queue = queue.Queue()
        self.stop_requested = threading.Event()
        self.results = []

        self._build_ui()
        self.after(200, self._poll_queue)

    def _build_ui(self):
        # Main container with padding
        main_container = ttk.Frame(self, padding="10")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid weights
        main_container.columnconfigure(0, weight=1)
        main_container.rowconfigure(2, weight=1)
        main_container.rowconfigure(4, weight=3)

        # Title
        title_label = ttk.Label(main_container, text="Check Zalo Number Tool - Lam Quang Dai Company", 
                               font=("Arial", 16, "bold"), foreground="#2c3e50")
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 15), sticky=tk.W)

        # Control panel
        control_frame = ttk.LabelFrame(main_container, text="Controls", padding="10")
        control_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        control_frame.columnconfigure(1, weight=1)

        # File selection
        ttk.Label(control_frame, text="CSV File:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.file_path_var = tk.StringVar()
        ttk.Entry(control_frame, textvariable=self.file_path_var, width=50).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        ttk.Button(control_frame, text="Browse", command=self.load_numbers, style='Info.TButton').grid(row=0, column=2, padx=5, pady=5)

        # Options
        options_frame = ttk.Frame(control_frame)
        options_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Label(options_frame, text="Batch size:").pack(side=tk.LEFT, padx=(0, 5))
        self.batch_var = tk.IntVar(value=20)
        ttk.Entry(options_frame, textvariable=self.batch_var, width=6).pack(side=tk.LEFT, padx=(0, 15))
        
        self.headless_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Headless Mode", variable=self.headless_var).pack(side=tk.LEFT, padx=(0, 15))

        # Buttons
        button_frame = ttk.Frame(control_frame)
        button_frame.grid(row=2, column=0, columnspan=3, pady=10)
        
        self.btn_login = ttk.Button(button_frame, text="Đăng nhập", command=self.start_login, style='Primary.TButton')
        self.btn_login.pack(side=tk.LEFT, padx=5)
        
        self.btn_continue = ttk.Button(button_frame, text="Tiếp tục kiểm tra", command=self.continue_check, 
                                      state=tk.DISABLED, style='Success.TButton')
        self.btn_continue.pack(side=tk.LEFT, padx=5)
        
        self.btn_stop = ttk.Button(button_frame, text="Dừng kiểm tra", command=self.stop_check, 
                                  state=tk.DISABLED, style='Danger.TButton')
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Lưu kết quả", command=self.save_results, style='Warning.TButton').pack(side=tk.LEFT, padx=5)

        # Results section
        results_frame = ttk.LabelFrame(main_container, text="Kết quả", padding="10")
        results_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)

        # Treeview for results with scrollbar
        tree_frame = ttk.Frame(results_frame)
        tree_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        columns = ("phone", "status", "name")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
        
        # Define columns
        self.tree.heading("phone", text="Số điện thoại", anchor=tk.W)
        self.tree.heading("status", text="Trạng thái", anchor=tk.W)
        self.tree.heading("name", text="Tên", anchor=tk.W)
        
        self.tree.column("phone", width=150, minwidth=150)
        self.tree.column("status", width=120, minwidth=120)
        self.tree.column("name", width=250, minwidth=150)
        
        # Add scrollbar
        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # Progress bar
        self.progress = ttk.Progressbar(results_frame, mode='indeterminate')
        self.progress.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        # Log section
        log_frame = ttk.LabelFrame(main_container, text="Nhật ký hoạt động", padding="10")
        log_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # Log text with scrollbar
        log_text_frame = ttk.Frame(log_frame)
        log_text_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_text_frame.columnconfigure(0, weight=1)
        log_text_frame.rowconfigure(0, weight=1)
        
        self.log_text = tk.Text(log_text_frame, height=8, wrap=tk.WORD)
        log_scroll = ttk.Scrollbar(log_text_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # Status bar
        self.status_var = tk.StringVar(value="Sẵn sàng")
        status_bar = ttk.Label(main_container, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E))

    def log(self, msg: str):
        timestamp = time.strftime('%H:%M:%S')
        self.log_text.insert(tk.END, f"[{timestamp}] {msg}\n")
        self.log_text.see(tk.END)
        self.status_var.set(msg)

    def load_numbers(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*")])
        if not path:
            return
        try:
            df = pd.read_csv(path)
            if 'phone' not in df.columns:
                messagebox.showerror("Lỗi", "CSV phải có cột 'phone'")
                return
            self.phone_numbers = df['phone'].astype(str).str.strip().tolist()
            self.file_path_var.set(os.path.basename(path))
            self.log(f"Đã tải {len(self.phone_numbers)} số từ {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể đọc file: {e}")

    def start_login(self):
        if ZaloChecker is None:
            messagebox.showerror("Lỗi", "Không tìm thấy lớp ZaloChecker.")
            return
        
        # Kiểm tra xem đã tải số điện thoại chưa
        if not hasattr(self, 'phone_numbers') or not self.phone_numbers:
            messagebox.showerror("Lỗi", "Chưa tải danh sách số điện thoại.")
            return
            
        # reset
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.results = []
        self.stop_requested.clear()

        headless = bool(self.headless_var.get())
        
        # Tạo instance mới của ZaloChecker
        self.checker = ZaloChecker(headless=headless)
        
        # Hiển thị thông báo hướng dẫn đăng nhập
        messagebox.showinfo("Hướng dẫn đăng nhập", 
                           "1. Trình duyệt sẽ mở ra trang Zalo\n"
                           "2. Vui lòng đăng nhập thủ công vào tài khoản Zalo của bạn\n"
                           "3. Sau khi đăng nhập thành công, nhấn nút 'Tiếp tục kiểm tra'")
        
        # Mở trình duyệt để đăng nhập
        try:
            self.checker.driver.get("https://chat.zalo.me/")
            self.log("Đã mở trình duyệt, vui lòng đăng nhập thủ công...")
            self.btn_continue.config(state=tk.NORMAL)
            self.btn_login.config(state=tk.DISABLED)
        except Exception as e:
            self.log(f"Lỗi khi mở trình duyệt: {e}")
            messagebox.showerror("Lỗi", f"Không thể mở trình duyệt: {e}")

    def continue_check(self):
        if not hasattr(self, 'phone_numbers') or not self.phone_numbers:
            messagebox.showerror("Lỗi", "Chưa tải danh sách số.")
            return
            
        # Kiểm tra xem trình duyệt có còn hoạt động không
        try:
            # Thử lấy URL hiện tại để kiểm tra kết nối
            current_url = self.checker.driver.current_url
            self.log(f"Trình duyệt đang ở: {current_url}")
            
            # Kiểm tra xem có phải đang ở trang Zalo không
            if "zalo.me" not in current_url:
                self.log("Cảnh báo: Có vẻ như không ở trang Zalo. Vui lòng đảm bảo đã đăng nhập.")
                if not messagebox.askyesno("Xác nhận", "Có vẻ như bạn chưa ở trang Zalo. Bạn có chắc chắn muốn tiếp tục?"):
                    return
        except Exception as e:
            self.log(f"Lỗi kiểm tra trình duyệt: {e}. Có thể trình duyệt đã đóng.")
            if messagebox.askyesno("Lỗi trình duyệt", "Trình duyệt có vẻ không hoạt động. Bạn có muốn thử đăng nhập lại?"):
                self.start_login()
                return
            else:
                return
                
        batch_size = int(self.batch_var.get()) if self.batch_var.get() > 0 else 20
        self.worker_thread = threading.Thread(
            target=self._worker, args=(self.phone_numbers, batch_size), daemon=True
        )
        self.worker_thread.start()
        self.btn_stop.config(state=tk.NORMAL)
        self.btn_continue.config(state=tk.DISABLED)
        self.progress.start()
        self.log("Bắt đầu kiểm tra số điện thoại...")

    def start_check(self):
        if ZaloChecker is None:
            messagebox.showerror("Lỗi", "Không tìm thấy lớp ZaloChecker. Hãy chắc rằng file module có tên zalo_checker_module.py hoặc zalo_checker.py và lớp ZaloChecker có sẵn.")
            return
        if not hasattr(self, 'phone_numbers') or not self.phone_numbers:
            messagebox.showerror("Lỗi", "Chưa tải danh sách số. Vui lòng tải CSV trước.")
            return
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning("Đang chạy", "Đang chạy rồi")
            return

        # reset
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.results = []
        self.stop_requested.clear()

        headless = bool(self.headless_var.get())
        batch_size = int(self.batch_var.get()) if self.batch_var.get() > 0 else 20

        # Create checker instance
        self.checker = ZaloChecker(headless=headless)

        # Launch worker thread
        self.worker_thread = threading.Thread(target=self._worker, args=(self.phone_numbers, batch_size), daemon=True)
        self.worker_thread.start()
        self.btn_stop.config(state=tk.NORMAL)
        self.progress.start()
        self.log("Bắt đầu kiểm tra...")

    def stop_check(self):
        if not self.worker_thread or not self.worker_thread.is_alive():
            return
        self.stop_requested.set()
        # best-effort: try to close browser to interrupt
        try:
            if self.checker:
                self.checker.close()
                self.log("Yêu cầu dừng: đã gọi checker.close() (nỗ lực dừng)")
        except Exception as e:
            self.log(f"Lỗi khi gọi close(): {e}")
        self.btn_stop.config(state=tk.DISABLED)
        self.progress.stop()

    # Trong class App của file UI, cập nhật phương thức _worker
    def _worker(self, phone_numbers, batch_size):
        try:
            total = len(phone_numbers)
            for idx, phone in enumerate(phone_numbers, start=1):
                if self.stop_requested.is_set():
                    self.worker_queue.put(("log", "Đã yêu cầu dừng - thoát worker"))
                    break

                # Sử dụng phương pháp URL trực tiếp thay vì phương pháp cũ
                res = self.checker.check_phone_number_direct_url(str(phone).strip())
                self.results.append(res)
                self.worker_queue.put(("result", res))
                self.worker_queue.put(("progress", (idx, total)))

                # Save intermediate batch
                if idx % batch_size == 0:
                    filename = f"zalo_results_batch_{idx//batch_size}.csv"
                    pd.DataFrame(self.results).to_csv(filename, index=False, encoding='utf-8-sig')
                    self.worker_queue.put(("log", f"Đã lưu batch {idx//batch_size} -> {filename}"))

            # final save
            if not self.stop_requested.is_set():
                pd.DataFrame(self.results).to_csv("zalo_results_final.csv", index=False, encoding='utf-8-sig')
                self.worker_queue.put(("log", "Đã lưu kết quả cuối cùng vào zalo_results_final.csv"))

        except Exception as e:
            self.worker_queue.put(("log", f"Lỗi worker: {e}"))
        finally:
            self.worker_queue.put(("done", None))

    def _poll_queue(self):
        try:
            while True:
                item = self.worker_queue.get_nowait()
                typ, data = item
                if typ == 'log':
                    self.log(data)
                elif typ == 'result':
                    self._add_result_to_tree(data)
                elif typ == 'progress':
                    idx, total = data
                    self.title(f"Zalo Checker - {idx}/{total}")
                elif typ == 'enable_continue':
                    self.btn_continue.config(state=tk.NORMAL)
                    self.btn_login.config(state=tk.DISABLED)
                elif typ == 'enable_login':
                    self.btn_login.config(state=tk.NORMAL)
                elif typ == 'done':
                    self.btn_stop.config(state=tk.DISABLED)
                    self.btn_continue.config(state=tk.DISABLED)
                    self.progress.stop()
                    self.log('Hoàn thành kiểm tra')
                    self.title("Zalo Checker - Hoàn thành")
        except queue.Empty:
            pass
        finally:
            self.after(200, self._poll_queue)

    def _add_result_to_tree(self, res: dict):
        phone = res.get('phone', '')
        status = res.get('status', '')
        name = res.get('name', '')
        
        # Add color coding based on status
        tags = ()
        if status == "Có Zalo":
            tags = ('success',)
        elif status == "Không có Zalo":
            tags = ('warning',)
        elif "Error" in status:
            tags = ('error',)
            
        self.tree.insert('', tk.END, values=(phone, status, name), tags=tags)
        
        # Configure tag colors
        self.tree.tag_configure('success', background='#d4edda')
        self.tree.tag_configure('warning', background='#fff3cd')
        self.tree.tag_configure('error', background='#f8d7da')

    def save_results(self):
        if not self.results:
            messagebox.showinfo("Không có kết quả", "Chưa có kết quả để lưu")
            return
        path = filedialog.asksaveasfilename(
            defaultextension='.csv', 
            filetypes=[('CSV files', '*.csv')],
            initialfile=f"zalo_results_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        )
        if not path:
            return
        try:
            pd.DataFrame(self.results).to_csv(path, index=False, encoding='utf-8-sig')
            self.log(f"Đã lưu kết quả vào {path}")
            messagebox.showinfo("Đã lưu", f"Đã lưu kết quả vào {path}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể lưu file: {e}")


if __name__ == '__main__':
    app = App()
    app.mainloop()