from flask import Flask, jsonify
import platform
import socket
from datetime import datetime

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <h1>🚀 Welcome to My Docker Flask App</h1>
    <p>This application is running inside a Docker container.</p>

    <h3>Available Endpoints</h3>

    <ul>
        <li><a href="/about">About</a></li>
        <li><a href="/system">System Info</a></li>
        <li><a href="/health">Health Check</a></li>
        <li><a href="/time">Current Time</a></li>
    </ul>
    """

@app.route("/about")
def about():
    return jsonify({
        "project": "Flask Docker Application",
        "developer": "Sanjit Bhagat",
        "technology": "Python, Flask, Docker"
    })

@app.route("/system")
def system():
    return jsonify({
        "hostname": socket.gethostname(),
        "operating_system": platform.system(),
        "python_version": platform.python_version()
    })

@app.route("/health")
def health():
    return jsonify({
        "status": "UP",
        "message": "Application is running successfully"
    })

@app.route("/time")
def time():
    return jsonify({
        "current_time": datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
