# client.py
# Gereksinimler: pip install flask requests
import socket, threading, json, os, sys, time, subprocess, webbrowser, requests, string
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import simpledialog, messagebox

TOKEN = "superdupersecrettoken"
HTTP_PORT = 8080
POSSIBLE_SERVERS = [
    "remotecontrol-9hw8.onrender.com:5000"
]

app = Flask(__name__)
# task_queue: list of dicts {run_at: datetime, run_at_iso: str, url: str}
task_queue = []
server_ip = None
server_port = None

# ---------------- Client File helpers ----------------
def find_disk_root_file(basename=".remote_client_name", folder_name="RemoteClient"):
    candidates = []
    drive_root = None
    try:
        drive, _ = os.path.splitdrive(os.getcwd())
        if drive:
            drive_root = os.path.join(drive + os.sep)
        else:
            drive_root = os.sep
    except:
        drive_root = os.sep
    candidates.append(drive_root)

    if sys.platform.startswith("win"):
        for d in string.ascii_uppercase:
            candidates.append(d + ":\\")
        candidates += [os.environ.get("PUBLIC", "C:\\Users\\Public")]
    else:
        candidates += ["/sdcard", "/storage/emulated/0", "/mnt", "/media", "/", "/opt", "/var/tmp", "/tmp"]

    for root in candidates:
        if not root:
            continue
        try:
            root = os.path.abspath(root)
            target_dir = os.path.join(root, folder_name)
            os.makedirs(target_dir, exist_ok=True)
            test_path = os.path.join(target_dir, ".write_test")
            with open(test_path, "w", encoding="utf-8") as tf:
                tf.write("ok")
            os.remove(test_path)
            return os.path.join(target_dir, basename)
        except Exception:
            continue

    try:
        fallback = os.path.join(os.path.expanduser("~"), folder_name)
        os.makedirs(fallback, exist_ok=True)
        return os.path.join(fallback, basename)
    except Exception:
        return os.path.join(os.getcwd(), basename)

CLIENT_FILE = find_disk_root_file()
print(f"[client] using client file path: {CLIENT_FILE}")

# ---------------- Tkinter toast + client name (zorunlu) ----------------
root = tk.Tk()
root.withdraw()  # gizle background

def show_toast(message, duration=2000):
    toast = tk.Toplevel()
    toast.overrideredirect(True)
    toast.configure(bg="#222")
    label = tk.Label(toast, text=message, fg="white", bg="#222", font=("Arial", 12))
    label.pack(padx=10, pady=5)
    toast.update_idletasks()
    w = toast.winfo_width()
    h = toast.winfo_height()
    ws = toast.winfo_screenwidth()
    hs = toast.winfo_screenheight()
    x = (ws // 2) - (w // 2)
    y = (hs // 2) - (h // 2)
    toast.geometry(f"{w}x{h}+{x}+{y}")
    toast.after(duration, toast.destroy)

if os.path.exists(CLIENT_FILE):
    with open(CLIENT_FILE, "r", encoding="utf-8") as f:
        CLIENT_NAME = f.read().strip()
    show_toast(f"{CLIENT_NAME} çalışıyor", duration=1500)
    root.after(1700, root.destroy)
else:
    CLIENT_NAME = None
    while not CLIENT_NAME:
        CLIENT_NAME = simpledialog.askstring("LAN Remote", "Client ismini girin:")
        if CLIENT_NAME:
            CLIENT_NAME = CLIENT_NAME.strip()
        if not CLIENT_NAME:
            messagebox.showwarning("Hata", "Client ismi boş olamaz!")
    os.makedirs(os.path.dirname(CLIENT_FILE), exist_ok=True)
    with open(CLIENT_FILE, "w", encoding="utf-8") as f:
        f.write(CLIENT_NAME)
    show_toast(f"{CLIENT_NAME} çalışıyor", duration=1500)
    root.after(1700, root.destroy)

root.mainloop()

# ---------------- Konsol gizleme (Windows) ----------------
if os.name == 'nt':
    try:
        import ctypes
        whnd = ctypes.windll.kernel32.GetConsoleWindow()
        if whnd != 0:
            ctypes.windll.user32.ShowWindow(whnd, 0)
    except:
        pass

# ---------------- URL açma ----------------
def shutil_which(name):
    for path in os.environ.get("PATH", "").split(os.pathsep):
        f = os.path.join(path, name)
        if os.path.isfile(f) and os.access(f, os.X_OK):
            return f
    return None

def open_url_platform(url):
    try:
        if shutil_which('termux-open'):
            subprocess.Popen(['termux-open', url])
            return True
    except:
        pass
    try:
        webbrowser.open_new_tab(url)
        return True
    except:
        return False

# ---------------- Task worker ----------------
def task_worker():
    while True:
        now = datetime.now()
        to_run = []
        for t in task_queue:
            if now >= t['run_at']:
                to_run.append(t)
        for t in to_run:
            print(f"[client] {datetime.now().strftime('%H:%M:%S')} - Opening scheduled URL: {t['url']}")
            open_url_platform(t['url'])
            try:
                task_queue.remove(t)
            except:
                pass
        time.sleep(1)

threading.Thread(target=task_worker, daemon=True).start()

# ---------------- Flask endpoints ----------------
@app.route('/open', methods=['POST'])
def open_endpoint():
    data = request.get_json() or {}
    token = data.get('token') or request.headers.get('X-Remote-Token')
    url = data.get('url')
    delay_sec = int(data.get('delay_sec', 0) or 0)
    if token != TOKEN:
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401
    if not url:
        return jsonify({'ok': False, 'error': 'No URL provided'}), 400

    run_at_dt = (datetime.now() + timedelta(seconds=delay_sec)).replace(microsecond=0)
    run_at_iso = run_at_dt.isoformat()
    task_entry = {'run_at': run_at_dt, 'run_at_iso': run_at_iso, 'url': url}
    # duplicate kontrol (aynı url+run_at varsa atlama)
    if not any(t['url'] == url and t['run_at_iso'] == run_at_iso for t in task_queue):
        task_queue.append(task_entry)
        print(f"[client] Task added: {url} -> scheduled for {run_at_iso}")

    # server'a bildir (server /add_task ile task kaydetsin)
    global server_ip, server_port
    if server_ip:
        try:
            requests.post(f"http://{server_ip}:{server_port}/add_task", json={
                "token": TOKEN,
                "url": url,
                "run_at": run_at_iso
            }, timeout=2)
        except:
            pass

    return jsonify({'ok': True, 'scheduled_for': run_at_iso})

@app.route('/delete_task_by_runat', methods=['POST'])
def delete_task_by_runat():
    data = request.get_json() or {}
    url = data.get('url')
    run_at = data.get('run_at')
    removed = False
    for t in task_queue[:]:
        if t['url'] == url and t['run_at_iso'] == run_at:
            try:
                task_queue.remove(t)
                removed = True
                print(f"[client] Task removed (run_at): {url} @ {run_at}")
            except:
                pass
    return jsonify({'ok': removed})

# backward compatibility (sil URL ile)
@app.route('/delete_task_by_url', methods=['POST'])
def delete_task_by_url():
    data = request.get_json() or {}
    url = data.get('url')
    removed = False
    for t in task_queue[:]:
        if t['url'] == url:
            try:
                task_queue.remove(t)
                removed = True
                print(f"[client] Task removed (url): {url}")
            except:
                pass
    return jsonify({'ok': removed})

# ---------------- server register ----------------
def register_with_server(ip, port):
    try:
        url = f"https://{ip}:{port}/register"  # cloud server HTTPS
        data = {"name": CLIENT_NAME}
        resp = requests.post(url, json=data, timeout=5, verify=False)  # SSL hatasını yoksay
        if resp.status_code == 200:
            print(f"[client] Registered with server {ip}:{port}")
            return True
    except Exception as e:
        print(f"[client] Register failed: {e}")
    return False

def discover_server():
    global server_ip, server_port
    for s in POSSIBLE_SERVERS:
        ip, port = s.split(":")
        port = int(port)
        if register_with_server(ip, port):
            server_ip, server_port = ip, port
            return ip, port
    return None, None

def auto_register_loop(ip, port):
    while True:
        register_with_server(ip, port)
        time.sleep(5)

# ---------------- main loop ----------------
def main_loop():
    while True:
        discover_server()
        if server_ip:
            threading.Thread(target=auto_register_loop, args=(server_ip, server_port), daemon=True).start()
            break
        else:
            print("[client] ⚠ Server bulunamadı, 5 saniye sonra tekrar denenecek...")
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=main_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=HTTP_PORT)
