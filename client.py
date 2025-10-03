# client_sync.pyw
# Gereksinimler: pip install flask requests
import socket, threading, json, os, sys, time, subprocess, webbrowser, requests, string
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import simpledialog, messagebox

TOKEN = "superdupersecrettoken"
HTTP_PORT = 8080
POSSIBLE_SERVERS = [
    "remotecontrol-9hw8.onrender.com"
]

app = Flask(__name__)
task_queue = []
server_ip = None
server_port = 443  # HTTPS port
CLIENT_NAME = None

# ---------------- Client Name / File ----------------
def find_disk_root_file(basename=".remote_client_name", folder_name="RemoteClient"):
    candidates = []
    drive_root = os.path.abspath(os.sep)
    candidates.append(drive_root)
    if sys.platform.startswith("win"):
        for d in string.ascii_uppercase:
            candidates.append(d + ":\\")
        candidates += [os.environ.get("PUBLIC", "C:\\Users\\Public")]
    else:
        candidates += ["/sdcard", "/storage/emulated/0", "/mnt", "/media", "/", "/tmp"]

    for root in candidates:
        try:
            target_dir = os.path.join(root, folder_name)
            os.makedirs(target_dir, exist_ok=True)
            return os.path.join(target_dir, basename)
        except:
            continue
    return os.path.join(os.getcwd(), basename)

CLIENT_FILE = find_disk_root_file()

# ---------------- Tkinter Toast ----------------
def show_toast(message, duration=2000):
    root = tk.Tk()
    root.withdraw()
    toast = tk.Toplevel(root)
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
    root.after(duration + 100, root.destroy)
    root.mainloop()

if os.path.exists(CLIENT_FILE):
    with open(CLIENT_FILE, "r", encoding="utf-8") as f:
        CLIENT_NAME = f.read().strip()
    show_toast(f"{CLIENT_NAME} çalışıyor", duration=1500)
else:
    while not CLIENT_NAME:
        root = tk.Tk()
        root.withdraw()
        CLIENT_NAME = simpledialog.askstring("LAN Remote", "Client ismini girin:")
        if CLIENT_NAME:
            CLIENT_NAME = CLIENT_NAME.strip()
        if not CLIENT_NAME:
            messagebox.showwarning("Hata", "Client ismi boş olamaz!")
        root.destroy()
    os.makedirs(os.path.dirname(CLIENT_FILE), exist_ok=True)
    with open(CLIENT_FILE, "w", encoding="utf-8") as f:
        f.write(CLIENT_NAME)
    show_toast(f"{CLIENT_NAME} çalışıyor", duration=1500)

# ---------------- URL açma ----------------
def open_url_platform(url):
    try:
        subprocess.Popen(['termux-open', url])
        return True
    except:
        pass
    try:
        webbrowser.open_new_tab(url)
        return True
    except:
        return False

# ---------------- Task Worker ----------------
def task_worker():
    while True:
        now = datetime.now()
        to_run = []
        for t in task_queue:
            if now >= t['run_at']:
                to_run.append(t)
        for t in to_run:
            open_url_platform(t['url'])
            try:
                task_queue.remove(t)
            except:
                pass
        time.sleep(1)

threading.Thread(target=task_worker, daemon=True).start()

# ---------------- Flask Endpoints ----------------
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
    if not any(t['url'] == url and t['run_at_iso'] == run_at_iso for t in task_queue):
        task_queue.append({'run_at': run_at_dt, 'run_at_iso': run_at_iso, 'url': url})

    return jsonify({'ok': True, 'scheduled_for': run_at_iso})

# ---------------- Server Discovery / Register ----------------
def register_with_server(host):
    global server_ip
    try:
        url = f"https://{host}/register"
        resp = requests.post(url, json={"name": CLIENT_NAME}, timeout=5, verify=True)
        if resp.status_code == 200:
            server_ip = host
            return True
    except:
        pass
    return False

def discover_server():
    for s in POSSIBLE_SERVERS:
        if register_with_server(s):
            return True
    return False

def auto_register_loop():
    while True:
        if server_ip:
            try:
                requests.post(f"https://{server_ip}/register", json={"name": CLIENT_NAME}, timeout=5, verify=True)
            except:
                pass
        time.sleep(5)

# ---------------- Server Task Sync ----------------
def fetch_tasks_loop():
    while True:
        if server_ip:
            try:
                r = requests.get(f"https://{server_ip}/tasks_for_client?token={TOKEN}", timeout=5, verify=True)
                if r.ok:
                    server_tasks = r.json().get('tasks', [])
                    for t in server_tasks:
                        if not any(existing['url'] == t['url'] and existing['run_at_iso'] == t['run_at'] for existing in task_queue):
                            task_queue.append({
                                'url': t['url'],
                                'run_at': datetime.fromisoformat(t['run_at']),
                                'run_at_iso': t['run_at']
                            })
            except:
                pass
        time.sleep(3)

# ---------------- Main Loop ----------------
def main_loop():
    while not discover_server():
        time.sleep(5)
    threading.Thread(target=auto_register_loop, daemon=True).start()
    threading.Thread(target=fetch_tasks_loop, daemon=True).start()

if __name__ == "__main__":
    threading.Thread(target=main_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=HTTP_PORT)
