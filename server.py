# server.py
# Gereksinimler: pip install flask requests
from flask import Flask, jsonify, request, render_template
import socket, requests, time
from datetime import datetime, timedelta

TOKEN = "superdupersecrettoken"
app = Flask(__name__)
devices = {}  # ip -> {"name":..., "http_port":..., "last_seen":..., "tasks":[{"url","run_at"}]}

@app.route('/')
def ui():
    # ui.html dosyasını templates klasörüne koymalısın
    return render_template("ui.html")

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    name = data.get('name')
    ip = request.remote_addr
    if name:
        devices[ip] = devices.get(ip, {"tasks":[]})
        devices[ip].update({
            "name": name,
            "ip": ip,
            "http_port": 8080,
            "last_seen": time.time()
        })
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "No name"}), 400

@app.route('/devices')
def get_devices():
    now = time.time()
    # temizle (10s görmezden gelme)
    for ip, d in list(devices.items()):
        if now - d.get("last_seen", 0) > 10:
            devices.pop(ip, None)
    # tasks alanının garantilenmesi
    for ip, d in devices.items():
        if "tasks" not in d:
            d["tasks"] = []
    return jsonify(list(devices.values()))

@app.route('/open', methods=['POST'])
def open_on_clients():
    data = request.get_json() or {}
    ips = data.get('ips') or []
    url = data.get('url')
    delay_sec = int(data.get('delay_sec', 0) or 0)
    results = []
    if not url:
        return jsonify({'error': 'no url'}), 400

    for ip in ips:
        try:
            target = f"http://{ip}:8080/open"
            r = requests.post(target, json={'token': TOKEN, 'url': url, 'delay_sec': delay_sec}, timeout=4, verify=False)
            resp = {}
            try:
                resp = r.json()
            except:
                pass
            results.append({'ip': ip, 'status': r.status_code, 'resp': resp})

            # server tarafında gözüksün diye task ekle (ISO second precision)
            run_at = (datetime.now() + timedelta(seconds=delay_sec)).replace(microsecond=0)
            run_at_iso = run_at.isoformat()
            devices.setdefault(ip, {}).setdefault("tasks", [])
            if not any(t['url'] == url and t['run_at'] == run_at_iso for t in devices[ip]["tasks"]):
                devices[ip]["tasks"].append({"url": url, "run_at": run_at_iso})
        except Exception as e:
            results.append({'ip': ip, 'error': str(e)})

    return jsonify({'results': results})

@app.route('/add_task', methods=['POST'])
def add_task_from_client():
    data = request.get_json() or {}
    token = data.get('token')
    ip = request.remote_addr
    url = data.get('url')
    run_at = data.get('run_at')
    if token != TOKEN:
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401
    if not url or not run_at:
        return jsonify({'ok': False, 'error': 'Missing data'}), 400
    if ip in devices:
        if not any(t['url'] == url and t['run_at'] == run_at for t in devices[ip].get("tasks", [])):
            devices[ip].setdefault("tasks", []).append({"url": url, "run_at": run_at})
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'error': 'Device not registered'}), 400

@app.route('/delete_task', methods=['POST'])
def delete_task():
    data = request.get_json() or {}
    ip = data.get('ip')
    index = data.get('index')
    if ip in devices and "tasks" in devices[ip] and 0 <= int(index) < len(devices[ip]["tasks"]):
        task = devices[ip]["tasks"].pop(int(index))
        # client'e bildir; client run_at ile silme yapacak
        try:
            requests.post(f"http://{ip}:8080/delete_task_by_runat", json={
                "url": task["url"],
                "run_at": task["run_at"]
            }, timeout=2, verify=False)
        except:
            pass
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 400

if __name__ == '__main__':
    print("Server çalışıyor! UI: port 5000")
    app.run(host='0.0.0.0', port=5000)
