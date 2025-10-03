# client.py
# Gereksinimler: pip install requests python-dotenv
import requests, threading, time, webbrowser, os, sys
from datetime import datetime
from dotenv import load_dotenv
import tkinter as tk
from tkinter import simpledialog, messagebox
import ctypes

# --- Konsolu gizle (Windows) ---
if os.name == 'nt':
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

load_dotenv()
TOKEN = os.getenv("TOKEN")
SERVER_URL = os.getenv("SERVER_URL")  # Örn: https://myserver.com:5000
CLIENT_NAME = os.getenv("CLIENT_NAME", "")

# --- Tkinter ile client name input ---
root = tk.Tk()
root.withdraw()  # Ana pencereyi gizle

while not CLIENT_NAME:
    CLIENT_NAME = simpledialog.askstring("Client Name", "Enter client name:", parent=root)
    if CLIENT_NAME is None:  # kullanıcı kapatmaya çalıştıysa
        messagebox.showinfo("Info", "You must enter a client name to continue.")
        continue

# --- Gösterim popup ---
messagebox.showinfo("Running", f"{CLIENT_NAME} is running")

task_queue = []

def register():
    try:
        requests.post(f"{SERVER_URL}/register", json={"name": CLIENT_NAME}, timeout=5)
    except:
        pass

def fetch_tasks():
    while True:
        try:
            r = requests.get(f"{SERVER_URL}/tasks_for_client", params={"token": TOKEN, "name": CLIENT_NAME}, timeout=5)
            if r.ok:
                server_tasks = r.json().get("tasks", [])
                for t in server_tasks:
                    if not any(existing["url"] == t["url"] and existing["run_at_iso"] == t["run_at_iso"] for existing in task_queue):
                        task_queue.append({
                            "url": t["url"],
                            "run_at": datetime.fromisoformat(t["run_at_iso"]),
                            "run_at_iso": t["run_at_iso"]
                        })
        except Exception as e:
            pass
        time.sleep(3)

def task_worker():
    while True:
        now = datetime.now()
        to_run = [t for t in task_queue if t["run_at"] <= now]
        for t in to_run:
            try:
                webbrowser.open_new_tab(t["url"])
            except:
                pass
            task_queue.remove(t)
        time.sleep(1)

threading.Thread(target=fetch_tasks, daemon=True).start()
threading.Thread(target=task_worker, daemon=True).start()
register()

# --- Sonsuz döngü ---
while True:
    time.sleep(10)
