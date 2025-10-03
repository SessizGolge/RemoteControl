# server.py
# Gereksinimler: pip install flask python-dotenv
from flask import Flask, request, jsonify, render_template
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("SERVER_PORT", 5000))

app = Flask(__name__)

# Global storage (basit, memory-based, production için DB lazım)
clients = {}  # name -> {ip, last_seen, tasks: [{url, run_at_iso}]}

@app.route('/')
def index():
    return render_template('ui.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    name = data.get("name")
    if not name:
        return jsonify({"ok": False, "error": "No name"}), 400
    clients[name] = clients.get(name, {"tasks": []})
    clients[name]["last_seen"] = datetime.now().isoformat()
    return jsonify({"ok": True})

@app.route('/tasks_for_client', methods=['GET'])
def tasks_for_client():
    token = request.args.get("token")
    client_name = request.args.get("name")
    if token != TOKEN:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    if client_name not in clients:
        return jsonify({"ok": False, "error": "Unknown client"}), 404
    return jsonify({"ok": True, "tasks": clients[client_name]["tasks"]})

@app.route('/add_task', methods=['POST'])
def add_task():
    data = request.get_json() or {}
    token = data.get("token")
    if token != TOKEN:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    client_names = data.get("clients") or []
    url = data.get("url")
    run_at_iso = data.get("run_at_iso")  # datetime string

    if not url or not client_names or not run_at_iso:
        return jsonify({"ok": False, "error": "Missing data"}), 400

    for c in client_names:
        if c not in clients:
            clients[c] = {"tasks": []}
        # Aynı task tekrar eklenmesin
        if not any(t["url"] == url and t["run_at_iso"] == run_at_iso for t in clients[c]["tasks"]):
            clients[c]["tasks"].append({"url": url, "run_at_iso": run_at_iso})
    return jsonify({"ok": True})

@app.route('/delete_task', methods=['POST'])
def delete_task():
    data = request.get_json() or {}
    token = data.get("token")
    if token != TOKEN:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    client_name = data.get("client")
    run_at_iso = data.get("run_at_iso")
    if not client_name or not run_at_iso or client_name not in clients:
        return jsonify({"ok": False, "error": "Missing or invalid data"}), 400
    clients[client_name]["tasks"] = [t for t in clients[client_name]["tasks"] if t["run_at_iso"] != run_at_iso]
    return jsonify({"ok": True})

@app.route('/devices', methods=['GET'])
def devices():
    return jsonify([{"name": k, "tasks": v["tasks"]} for k, v in clients.items()])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
