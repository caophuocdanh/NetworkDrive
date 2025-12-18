import tkinter as tk
from tkinter import ttk, messagebox
import win32wnet
import win32netcon
import win32api
import win32file
import win32net # Thư viện mới để lấy share
import string
import threading
import queue
from tkinter import font

import sys
import os

# Helper function to find resources in PyInstaller bundle
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class NetworkDriveManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Network Drive Manager")
        self.root.geometry("600x310") # Kích thước mới nhỏ gọn hơn
        self.root.resizable(False, False)

        try:
            # Use resource_path to find the icon
            self.root.iconbitmap(resource_path('icon.ico'))
        except tk.TclError:
            print("Warning: icon.ico not found or could not be loaded.")

        self.server_var = tk.StringVar()
        self.user_var = tk.StringVar()
        self.pass_var = tk.StringVar()
        self.drive_letter_var = tk.StringVar()
        self.shares_var = tk.StringVar()
        self.reconnect_var = tk.BooleanVar(value=True) 

        self.task_queue = queue.Queue()
        self.create_widgets()
        
        self.root.after(100, self.process_queue)
        self.start_refresh_drive_list()

    def create_widgets(self):
        # Frame 1: Left Panel (Existing Network Drives) - Simplified layout
        frame1 = ttk.Labelframe(self.root, text="① Ổ đĩa mạng hiện có")
        frame1.place(x=10, y=10, width=340, height=290)
        
        columns = ("drive", "path", "user")
        self.tree = ttk.Treeview(frame1, columns=columns, show="headings")
        
        # --- Column setup ---
        self.tree.heading("drive", text="Ổ Đĩa")
        self.tree.heading("path", text="Đường Dẫn Mạng")
        self.tree.heading("user", text="User")
        
        # IMPORTANT: Set stretch=False for all columns to allow horizontal scroll to work with autofit
        self.tree.column("drive", width=50, minwidth=40, anchor='center', stretch=False)
        self.tree.column("path", width=170, minwidth=150, stretch=False)
        self.tree.column("user", width=80, minwidth=80, stretch=False)
        
        # --- Scrollbar setup ---
        vsb = ttk.Scrollbar(frame1, orient="vertical", command=self.tree.yview)
        self.hsb = ttk.Scrollbar(frame1, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=self.hsb.set)
        
        # --- Grid layout for all elements in frame1 ---
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        self.hsb.grid(row=1, column=0, sticky='ew')
        
        frame1.grid_rowconfigure(0, weight=1)
        frame1.grid_columnconfigure(0, weight=1)
        
        self.unmap_button = ttk.Button(frame1, text="Disconnect Drive", command=self.disconnect_selected)
        self.unmap_button.grid(row=2, column=0, columnspan=2, pady=5, sticky='ew')

        # Frame 2: Right Panel (Connect SMB to Server)
        frame2 = ttk.Labelframe(self.root, text="② Kết nối SMB tới máy chủ")
        frame2.place(x=360, y=10, width=230, height=290)
        
        ttk.Label(frame2, text="Server/IP:").place(x=5, y=10)
        self.entry_server = ttk.Entry(frame2, width=22, textvariable=self.server_var)
        self.entry_server.place(x=80, y=10)
        
        ttk.Label(frame2, text="Username:").place(x=5, y=40)
        self.entry_user = ttk.Entry(frame2, width=22, textvariable=self.user_var)
        self.entry_user.place(x=80, y=40)
        
        ttk.Label(frame2, text="Password:").place(x=5, y=70)
        self.entry_pass = ttk.Entry(frame2, show='*', width=22, textvariable=self.pass_var)
        self.entry_pass.place(x=80, y=70)
        
        self.connect_server_button = ttk.Button(frame2, text="Connect", command=self.list_shares)
        self.connect_server_button.place(x=80, y=105)
        
        ttk.Label(frame2, text="Chọn share:").place(x=5, y=140)
        self.combo_share = ttk.Combobox(frame2, state="readonly", width=18, textvariable=self.shares_var)
        self.combo_share.place(x=80, y=140)
        
        ttk.Label(frame2, text="Ký tự ổ đĩa:").place(x=5, y=175)
        self.combo_letter = ttk.Combobox(frame2, state="readonly", width=8, textvariable=self.drive_letter_var)
        self.combo_letter.place(x=80, y=175)
        
        self.map_button = ttk.Button(frame2, text="Map Drive", command=self.map_drive)
        self.map_button.place(x=80, y=220)

    # --- Wrapper methods to adapt UI to logic ---
    def disconnect_selected(self):
        self.start_unmap_drive()

    def list_shares(self):
        self.start_get_shares()

    def map_drive(self):
        self.start_map_drive()

    def set_ui_state(self, enabled):
        state = "normal" if enabled else "disabled"
        self.map_button.config(state=state)
        self.unmap_button.config(state=state)
        self.connect_server_button.config(state=state)

    def process_queue(self):
        try:
            task = self.task_queue.get_nowait()
            
            if task['type'] == 'refresh':
                self._update_drive_list(task.get('drives', []))
                self._update_available_drives(task.get('available', []))
                if 'error' in task: messagebox.showerror("Lỗi Quét Ổ Đĩa", task['error'])
            
            elif task['type'] == 'get_shares':
                self.shares_var.set('')
                self.combo_share['values'] = []
                if task['status'] == 'success':
                    shares = task.get('shares', [])
                    if shares:
                        self.combo_share['values'] = shares
                        self.shares_var.set(shares[0])
                        messagebox.showinfo("Thành công", f"Tìm thấy {len(shares)} thư mục share.")
                    else:
                        messagebox.showwarning("Thông báo", "Không tìm thấy thư mục share nào trên server.")
                else:
                    messagebox.showerror("Lỗi", task['message'])

            elif task['type'] == 'map':
                if task['status'] == 'success':
                    messagebox.showinfo("Thành công", task['message'])
                    self.pass_var.set("")
                    self.start_refresh_drive_list()
                else:
                    messagebox.showerror("Thất bại", task['message'])

            elif task['type'] == 'unmap':
                if task['status'] == 'success':
                    messagebox.showinfo("Thành công", task['message'])
                    self.start_refresh_drive_list()
                else:
                    messagebox.showerror("Lỗi", task['message'])
            
            self.set_ui_state(True)
        except queue.Empty:
            self.root.after(100, self.process_queue)
        else:
            self.root.after(100, self.process_queue)

    def start_get_shares(self):
        server = self.server_var.get()
        if not server:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập tên Server hoặc IP.")
            return
        self.set_ui_state(False)
        args = (server, self.user_var.get(), self.pass_var.get())
        threading.Thread(target=self._worker_get_shares, args=args, daemon=True).start()

    def _worker_get_shares(self, server, user, password):
        result = {'type': 'get_shares'}
        temp_conn = f"\\\\{server}\\ipc$"
        try:
            win32wnet.WNetCancelConnection2(temp_conn, 0, True)
        except: pass
        
        try:
            if user and password:
                net_resource_obj = win32wnet.NETRESOURCE()
                net_resource_obj.dwType = win32netcon.RESOURCETYPE_ANY
                net_resource_obj.lpRemoteName = temp_conn
                win32wnet.WNetAddConnection2(net_resource_obj, password, user, 0)
            
            shares_info, _, _ = win32net.NetShareEnum(server, 1)
            shares = [s['netname'] for s in shares_info if s['type'] == 0 and not s['netname'].endswith('$')]
            result['status'] = 'success'
            result['shares'] = shares
        except Exception as e:
            result['status'] = 'error'
            if hasattr(e, 'winerror'):
                result['message'] = self.analyze_error(e.winerror, e.strerror)
            else:
                result['message'] = str(e)
        finally:
            try: win32wnet.WNetCancelConnection2(temp_conn, 0, True)
            except: pass

        self.task_queue.put(result)

    def start_map_drive(self):
        server = self.server_var.get()
        drive_letter = self.drive_letter_var.get()
        share_name = self.shares_var.get()

        if not all([server, drive_letter, share_name]):
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập Server, chọn thư mục Share và ký tự ổ đĩa.")
            return
            
        remote_path = f"\\\\{server}\\{share_name}"
        
        self.set_ui_state(False)
        args = (drive_letter, remote_path, self.user_var.get(), self.pass_var.get(), self.reconnect_var.get())
        threading.Thread(target=self._worker_map_drive, args=args, daemon=True).start()
    
    def _worker_map_drive(self, local_drive, remote_path, user, password, reconnect):
        result = {'type': 'map'}
        net_resource_obj = win32wnet.NETRESOURCE()
        net_resource_obj.dwType = win32netcon.RESOURCETYPE_DISK
        net_resource_obj.lpLocalName = local_drive
        net_resource_obj.lpRemoteName = remote_path

        flags = win32netcon.CONNECT_UPDATE_PROFILE if reconnect else 0
        try:
            u = user if user.strip() else None
            p = password if password.strip() else None
            win32wnet.WNetAddConnection2(net_resource_obj, p, u, flags)
            result['status'] = 'success'
            result['message'] = f"Đã map ổ {local_drive} thành công!"
        except Exception as e:
            result['status'] = 'error'
            if hasattr(e, 'winerror'): result['message'] = self.analyze_error(e.winerror, e.strerror)
            else: result['message'] = str(e)
        self.task_queue.put(result)

    def start_refresh_drive_list(self):
        self.set_ui_state(False)
        threading.Thread(target=self._worker_refresh_drive_list, daemon=True).start()

    def _worker_refresh_drive_list(self):
        result = {'type': 'refresh', 'drives': [], 'available': []}
        try:
            drives = win32api.GetLogicalDriveStrings().split('\000')[:-1]
            for drive in drives:
                drive_letter = drive[:2]
                try:
                    if win32file.GetDriveType(drive) == win32file.DRIVE_REMOTE:
                        remote_path = win32wnet.WNetGetConnection(drive_letter)
                        user = win32wnet.WNetGetUser(drive_letter)
                        result['drives'].append((drive_letter, remote_path, user))
                except Exception:
                    pass # Bỏ qua các ổ đĩa lỗi hoặc đã ngắt kết nối
            result['available'] = self._get_available_drives()
        except Exception as e:
            result['error'] = str(e)
        self.task_queue.put(result)
    
    def _update_drive_list(self, drives):
        for item in self.tree.get_children(): self.tree.delete(item)
        for drive_item in drives: self.tree.insert("", "end", values=drive_item)
        self.root.update_idletasks() # Ensure widgets are updated before calculating sizes
        self._autofit_treeview_columns()
        # Force scrollbar update after autofit
        self.tree.xview_moveto(0)
        self.tree.yview_moveto(0) # Also reset vertical scroll
        self.hsb.set(*self.tree.xview()) # This forces the scrollbar to re-evaluate its range

    def _autofit_treeview_columns(self):
        font_obj = font.nametofont("TkDefaultFont")
        
        for col_id in self.tree['columns']:
            if col_id == "path": # Fix path column to 200
                self.tree.column(col_id, width=200, stretch=False) # Ensure stretch=False here too
                continue

            max_width = 0
            header_text = self.tree.heading(col_id, 'text')
            max_width = max(max_width, font_obj.measure(header_text) + 10) # Add padding
            
            col_idx = self.tree['columns'].index(col_id)
            for item_id in self.tree.get_children():
                item_values = self.tree.item(item_id, 'values')
                if col_idx < len(item_values):
                    value = item_values[col_idx]
                    item_width = font_obj.measure(str(value)) + 10
                    max_width = max(max_width, item_width)
            
            self.tree.column(col_id, width=max_width, stretch=False) # Ensure stretch=False here too


    def _update_available_drives(self, available):
        available.sort(reverse=True) # Sort in reverse order
        self.combo_letter['values'] = available
        if available and not self.drive_letter_var.get() in available:
            self.drive_letter_var.set(available[0])

    def _get_available_drives(self):
        used_letters = [d[0].upper() for d in win32api.GetLogicalDriveStrings().split('\000')[:-1]]
        return [char + ":" for char in string.ascii_uppercase if char not in used_letters]

    def start_unmap_drive(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showinfo("Thông báo", "Vui lòng chọn ổ đĩa cần ngắt kết nối trong danh sách.")
            return
        item_values = self.tree.item(selected_item, 'values')
        drive_letter = item_values[0]
        if messagebox.askyesno("Xác nhận", f"Bạn có chắc muốn ngắt kết nối ổ {drive_letter} không?"):
            self.set_ui_state(False)
            threading.Thread(target=self._worker_unmap_drive, args=(drive_letter,), daemon=True).start()

    def _worker_unmap_drive(self, drive_letter):
        result = {'type': 'unmap'}
        try:
            win32wnet.WNetCancelConnection2(drive_letter, win32netcon.CONNECT_UPDATE_PROFILE, True)
            result['status'] = 'success'
            result['message'] = f"Đã ngắt kết nối ổ {drive_letter} thành công."
        except Exception as e:
            result['status'] = 'error'
            result['message'] = f"Không thể ngắt kết nối: {e}"
        self.task_queue.put(result)

    def analyze_error(self, error_code, error_msg):
        error_map = {
            5: "Lỗi Quyền (Access Denied): Sai Username hoặc Password.",
            53: "Lỗi Mạng (Network Path Not Found): Không tìm thấy Server hoặc sai địa chỉ IP.",
            67: "Lỗi Tên Mạng (Bad Network Name): Tên share không hợp lệ.",
            85: "Lỗi Trùng Tên (Local Device Name Already in Use): Ký tự ổ đĩa đã được sử dụng.",
            86: "Lỗi Mật Khẩu (Invalid Password): Mật khẩu không đúng.",
            1219: "Lỗi Xung Đột Phiên (Multiple Connections): Đã có một kết nối tới server này bằng một tài khoản khác. Hãy ngắt tất cả kết nối cũ tới server và thử lại.",
            1326: "Lỗi Đăng Nhập (Logon Failure): Username hoặc password không đúng."
        }
        return error_map.get(error_code, f"Lỗi không xác định ({error_code}): {error_msg}")

if __name__ == "__main__":
    root = tk.Tk()
    app = NetworkDriveManager(root)
    root.mainloop()