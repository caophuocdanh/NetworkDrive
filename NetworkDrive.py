import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import ctypes
import logging
import re

# --- Cấu hình logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def get_mapped_drives():
    try:
        output = subprocess.check_output("net use", shell=True, text=True)
        logging.debug(f"[net use output]\n{output}")
        lines = output.strip().splitlines()
        drives = []
        parsing = False
        for line in lines:
            if re.match(r"^-{5,}", line):
                parsing = True
                continue
            if not parsing or not line.strip():
                continue
            match = re.match(r'^(OK|Disconnected|Unavailable)\s+([A-Z]:)\s+(\\\\.+)', line.strip())
            if match:
                status, local, remote = match.groups()
                remote_clean = remote.replace("Microsoft Windows Network", "").strip()
                parts = remote_clean.split("\\")
                unc_path = r"\\" + parts[2] + "\\" + parts[3] if len(parts) >= 4 else remote_clean
                drives.append((local, unc_path))
        logging.info(f"📦 Ổ đĩa mạng hiện tại: {drives}")
        return drives
    except Exception as e:
        logging.error(f"Lỗi lấy danh sách ổ đĩa mạng: {e}")
        return []

def disconnect_drive(drive_letter):
    try:
        subprocess.check_call(f'net use {drive_letter} /delete /y', shell=True)
        logging.info(f"🔌 Đã ngắt kết nối ổ đĩa {drive_letter}")
        return True
    except Exception as e:
        logging.error(f"Lỗi khi ngắt ổ đĩa {drive_letter}: {e}")
        return False

def list_shared_folders(server_ip):
    try:
        logging.info(f"📡 Đang liệt kê share từ máy chủ: {server_ip}")
        result = subprocess.check_output(
            ["net", "view", f"\\\\{server_ip}"],
            stderr=subprocess.STDOUT,
            text=True,
            shell=True
        )
        shared_folders = []
        lines = result.splitlines()
        parsing = False
        for line in lines:
            if '---' in line:
                parsing = True
                continue
            if parsing:
                match = re.match(r'^(.+?)\s{2,}Disk', line.strip())
                if match:
                    shared_folders.append(match.group(1))
        logging.info(f"📂 Share tìm thấy: {shared_folders}")
        return shared_folders
    except subprocess.CalledProcessError as e:
        logging.error(f"Lỗi khi chạy net view: {e.output}")
        return []

def get_available_drive_letters():
    import string
    from ctypes import windll
    used_letters = set()
    bitmask = windll.kernel32.GetLogicalDrives()
    for i in range(26):
        if bitmask & (1 << i):
            used_letters.add(chr(65 + i))
    available = [chr(i) for i in range(ord('Z'), ord('A') - 1, -1) if chr(i) not in used_letters]
    return available

def credential_exists(server):
    """Kiểm tra xem credential có tồn tại cho server không."""
    logging.info(f"🔎 Kiểm tra credential đã tồn tại cho '{server}'...")
    try:
        result = subprocess.check_output("cmdkey /list", shell=True, text=True)
        exists = any(server in line for line in result.splitlines())
        if exists:
            logging.info(f"✅ Tìm thấy credential có chứa '{server}'.")
        else:
            logging.info(f"ℹ️ Không có credential nào cho '{server}'.")
        return exists
    except Exception as e:
        logging.warning(f"⚠️ Không thể kiểm tra credential: {e}")
        return False


def manage_credentials(server, username, password):
    if credential_exists(server):
        try:
            logging.warning(f"⚠️ Credential cho '{server}' đã tồn tại. Đang xóa...")
            subprocess.call(f'cmdkey /delete:{server}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logging.info(f"✅ Đã xoá credential (nếu tồn tại).")
        except Exception as e:
            logging.error(f"❌ Không thể xóa credential cho {server}: {e}")
            # Không cần dừng chương trình – vì lỗi này không nghiêm trọng
            # return False

    try:
        logging.info(f"💾 Đang lưu thông tin xác thực cho Server={server}, User={username}")
        subprocess.check_call(f'cmdkey /add:{server} /user:{username} /pass:"{password}"', shell=True)
        logging.info(f"✅ Đã lưu/cập nhật thành công credential.")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"❌ Lỗi khi thêm credential cho {server}: {e}")
        messagebox.showerror("Lỗi Credential", f"Không thể lưu thông tin đăng nhập cho {server}.")
        return False


class NetworkDriveManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Network Drive Manager")
        self.geometry("675x305")
        self.resizable(False, False)

        self.reboot_needed = False  # 1. Thêm biến trạng thái
        self.protocol("WM_DELETE_WINDOW", self.on_closing) # 2. Bắt sự kiện đóng cửa sổ

        self.create_widgets()
        self.refresh_drive_list()

    def create_widgets(self):
        frame1 = ttk.LabelFrame(self, text="① Ổ đĩa mạng hiện có")
        frame1.place(x=10, y=10, width=340, height=280)
        columns = ("drive", "path")
        self.tree = ttk.Treeview(frame1, columns=columns, show="headings")
        self.tree.heading("drive", text="Ổ Đĩa")
        self.tree.heading("path", text="Đường Dẫn Mạng")
        self.tree.column("drive", width=50, anchor='center')
        self.tree.column("path", width=350)
        vsb = ttk.Scrollbar(frame1, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(frame1, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        frame1.grid_rowconfigure(0, weight=1)
        frame1.grid_columnconfigure(0, weight=1)
        btn_disconnect = ttk.Button(frame1, text="Disconnect Drive", command=self.disconnect_selected)
        btn_disconnect.grid(row=2, column=0, columnspan=2, pady=5, sticky='ew')

        frame2 = ttk.LabelFrame(self, text="② Kết nối SMB tới máy chủ")
        frame2.place(x=360, y=10, width=300, height=280)
        ttk.Label(frame2, text="Server/IP:").place(x=10, y=10)
        self.entry_server = ttk.Entry(frame2, width=28)
        self.entry_server.place(x=100, y=10)
        ttk.Label(frame2, text="Username:").place(x=10, y=40)
        self.entry_user = ttk.Entry(frame2, width=28)
        self.entry_user.place(x=100, y=40)
        ttk.Label(frame2, text="Password:").place(x=10, y=70)
        self.entry_pass = ttk.Entry(frame2, show='*', width=28)
        self.entry_pass.place(x=100, y=70)
        btn_list_shares = ttk.Button(frame2, text="Connect", command=self.list_shares)
        btn_list_shares.place(x=100, y=105)
        ttk.Label(frame2, text="Chọn share:").place(x=10, y=140)
        self.combo_share = ttk.Combobox(frame2, state="readonly", width=25)
        self.combo_share.place(x=100, y=140)
        ttk.Label(frame2, text="Ký tự ổ đĩa:").place(x=10, y=175)
        self.combo_letter = ttk.Combobox(frame2, state="readonly", width=10)
        self.combo_letter.place(x=100, y=175)
        btn_map = ttk.Button(frame2, text="Map Drive", command=self.map_drive)
        btn_map.place(x=100, y=220)

    def refresh_drive_list(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        drives = get_mapped_drives()
        for d, p in drives:
            self.tree.insert("", tk.END, values=(d, p))

    def disconnect_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Chưa chọn", "Vui lòng chọn ổ đĩa để ngắt kết nối.")
            return
        for item in selected:
            drive = self.tree.item(item)['values'][0]
            if messagebox.askyesno("Xác nhận", f"Bạn có chắc chắn muốn ngắt kết nối {drive}?"):
                if disconnect_drive(drive):
                    self.tree.delete(item)

    def list_shares(self):
        server = self.entry_server.get().strip()
        username = self.entry_user.get().strip()
        password = self.entry_pass.get().strip()

        # 1. Kiểm tra thông tin nhập
        if not server or not username or not password:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập đầy đủ IP máy chủ, Username và Password.")
            return

        # Kiểm tra xem credential có tồn tại TRƯỚC KHI thực hiện bất kỳ thay đổi nào không.
        # Nếu có, nghĩa là chúng ta sắp ghi đè lên nó.
        if credential_exists(server):
            logging.warning(f"Phát hiện credential đã tồn tại cho {server}. Gắn cờ yêu cầu khởi động lại.")
            self.reboot_needed = True

        # 2. Ngắt các thư mục mạng đã map đến IP này
        disconnected_count = 0
        try:
            logging.info(f"🧹 Đang kiểm tra các kết nối mapped tới máy chủ {server}...")
            output = subprocess.check_output("net use", shell=True, text=True)
            for line in output.splitlines():
                match = re.match(r'^(OK|Disconnected|Unavailable)\s+([A-Z]:)\s+(\\\\.+)', line.strip())
                if match:
                    drive_letter, unc_path = match.group(2), match.group(3)
                    if server in unc_path:
                        logging.info(f"⛔ Ngắt mapped drive {drive_letter} -> {unc_path}")
                        subprocess.call(f'net use {drive_letter} /delete /y', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        disconnected_count += 1
        except Exception as e:
            logging.warning(f"⚠️ Không thể kiểm tra ngắt kết nối ổ đĩa: {e}")

        if disconnected_count > 0:
            self.refresh_drive_list()
            messagebox.showinfo("Ngắt kết nối", f"Đã ngắt {disconnected_count} ổ đĩa mạng kết nối đến {server}.")

        # 3. Ping tới server
        try:
            subprocess.check_call(f"ping -n 1 {server}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            messagebox.showerror("Không kết nối được", f"Không thể ping đến máy chủ {server}.")
            return

        # 4. Thực hiện xác thực IPC$
        try:
            subprocess.check_call(
                ["net", "use", f"\\\\{server}\\IPC$", f"/user:{username}", password],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            logging.info(f"✅ Đã xác thực SMB IPC$ thành công với máy chủ {server}")
            messagebox.showinfo("Thành công", f"Đã kết nối xác thực tới {server}. Đang tải danh sách thư mục chia sẻ...")
        except subprocess.CalledProcessError:
            messagebox.showerror("Lỗi xác thực", f"Không thể xác thực với máy chủ {server}.\nKiểm tra lại Username và Password.")
            return

        # 5. Lưu credential
        if not manage_credentials(server, username, password):
            return

        # 6. Lấy danh sách share
        shares = list_shared_folders(server)
        if not shares:
            messagebox.showinfo("Không có share", "Không tìm thấy thư mục chia sẻ nào trên máy chủ.")
            subprocess.call(f'net use \\\\{server}\\IPC$ /delete /y', shell=True)
            return

        self.combo_share['values'] = shares
        if shares:
            self.combo_share.current(0)

        letters = get_available_drive_letters()
        if not letters:
            messagebox.showerror("Lỗi", "Không còn ký tự ổ đĩa trống.")
            return

        self.combo_letter['values'] = letters
        self.combo_letter.current(0)

        subprocess.call(f'net use \\\\{server}\\IPC$ /delete /y', shell=True)


    def map_drive(self):
        server = self.entry_server.get().strip()
        share = self.combo_share.get()
        letter = self.combo_letter.get().upper()
        if not server or not share or not letter:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng điền đầy đủ thông tin.")
            return
        letter = letter.rstrip(':')
        unc_path = f"\\\\{server}\\{share}"
        cmd = f'net use {letter}: "{unc_path}" /persistent:yes'
        logging.info(f"⚙️ Thực hiện ánh xạ: {cmd}")
        try:
            subprocess.check_call(cmd, shell=True)
            messagebox.showinfo("Thành công", f"Đã ánh xạ {letter}: đến {unc_path}")
            self.refresh_drive_list()
            letters = get_available_drive_letters()
            self.combo_letter['values'] = letters
            if letters: self.combo_letter.current(0)
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Lỗi", f"Không thể ánh xạ ổ đĩa.\n{e}")
    def on_closing(self):
        """Hàm tùy chỉnh xử lý sự kiện đóng cửa sổ."""
        if self.reboot_needed:
            messagebox.showinfo(
                "Thông báo quan trọng",
                "Bạn đã thay đổi thông tin xác thực cho một máy chủ đã kết nối trước đó.\n\n"
                "Cần khởi động lại máy để áp dụng hoàn toàn user mới và tránh lỗi kết nối tiềm ẩn."
            )
        self.destroy()

if __name__ == "__main__":
    app = NetworkDriveManager()
    app.mainloop()