# server.py
from flask import Flask, jsonify, request, render_template
import time
from datetime import datetime, timedelta
import requests
import uuid

TOKEN = "superdupersecrettoken"
app = Flask(__name__)

# devices = { client_id: {"name":..., "ip":..., "http_port":..., "last_seen":..., "tasks":[{"url","run_at"}]} }
devices = {}

@app.route('/')
def ui():
    return render_template("ui.html")

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    name = data.get('name')
    client_id = data.get('client_id') or str(uuid.uuid4())
    ip = request.remote_addr

    devices[client_id] = devices.get(client_id, {"tasks":[]})
    devices[client_id].update({
        "name": name,
        "ip": ip,
        "http_port": 8080,
        "last_seen": time.time(),
        "client_id": client_id
    })
    return jsonify({"ok": True, "client_id": client_id})

@app.route('/devices')
def get_devices():
    now = time.time()
    # offline clientları temizle (10s görmezden gelme)
    for cid, d in list(devices.items()):
        if now - d.get("last_seen", 0) > 10:
            devices.pop(cid, None)
    for cid, d in devices.items():
        d.setdefault("tasks", [])
    return jsonify(list(devices.values()))

@app.route('/open', methods=['POST'])
def open_on_clients():
    data = request.get_json() or {}
    client_ids = data.get('client_ids') or []
    url = data.get('url')
    delay_sec = int(data.get('delay_sec', 0) or 0)
    results = []

    if not url:
        return jsonify({'error': 'no url'}), 400

    for cid in client_ids:
        dev = devices.get(cid)
        if not dev:
            results.append({'client_id': cid, 'error': 'Device not found'})
            continue

        # task ekleme server RAM ve client persistence için
        run_at = (datetime.now() + timedelta(seconds=delay_sec)).replace(microsecond=0)
        run_at_iso = run_at.isoformat()
        dev.setdefault("tasks", [])
        if not any(t['url'] == url and t['run_at'] == run_at_iso for t in dev["tasks"]):
            dev["tasks"].append({"url": url, "run_at": run_at_iso})

        # client’e POST atmaya çalış
        try:
            target = f"http://{dev['ip']}:{dev['http_port']}/open"
            r = requests.post(target, json={'token': TOKEN, 'url': url, 'delay_sec': delay_sec}, timeout=4)
            resp = r.json() if r.ok else {}
            results.append({'client_id': cid, 'status': r.status_code, 'resp': resp})
        except Exception as e:
            results.append({'client_id': cid, 'error': str(e)})

    return jsonify({'results': results})

@app.route('/tasks_for_client')
def tasks_for_client():
    token = request.args.get('token')
    client_id = request.args.get('client_id')
    if token != TOKEN or client_id not in devices:
        return jsonify({'tasks': []}), 401
    return jsonify({'tasks': devices[client_id].get("tasks", [])})

@app.route('/delete_task', methods=['POST'])
def delete_task():
    data = request.get_json() or {}
    client_id = data.get('client_id')
    index = data.get('index')

    if client_id in devices and "tasks" in devices[client_id] and 0 <= int(index) < len(devices[client_id]["tasks"]):
        task = devices[client_id]["tasks"].pop(int(index))
        # client’e bildir
        try:
            requests.post(f"http://{devices[client_id]['ip']}:{devices[client_id]['http_port']}/delete_task_by_runat",
                          json={"url": task["url"], "run_at": task["run_at"]}, timeout=2)
        except:
            pass
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 400

if __name__ == "__main__":
    print("Server çalışıyor! UI: port 5000")
    app.run(host='0.0.0.0', port=5000)
