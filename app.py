from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from datetime import datetime
import os
import random

# --- 1. INITIALIZATION ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'volvoway_industrial_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///smart_bin.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# --- 2. DATABASE MODELS ---

class Bin(db.Model):
    """Stores the physical properties of each registered dustbin."""
    id = db.Column(db.String(20), primary_key=True) 
    supervisor = db.Column(db.String(100))
    lat = db.Column(db.Float, default=0.0)
    lon = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Telemetry(db.Model):
    """Logs every data packet sent by the hardware for history/analytics."""
    id = db.Column(db.Integer, primary_key=True)
    bin_id = db.Column(db.String(20), db.ForeignKey('bin.id'))
    fill_level = db.Column(db.Integer)
    status_msg = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Ensure database tables are created on startup
with app.app_context():
    db.create_all()
    print(">>> Municipal Central Database Initialized.")

# --- 3. WEB & API ROUTES ---

@app.route('/')
def index():
    """Renders the professional dashboard.html from the /templates folder."""
    return render_template('dashboard.html')

@app.route('/api/v1/bins', methods=['GET'])
def get_registered_bins():
    """Returns a list of all authorized nodes for the dashboard UI."""
    bins = Bin.query.all()
    return jsonify([
        {"id": b.id, "supervisor": b.supervisor, "lat": b.lat, "lon": b.lon} 
        for b in bins
    ])

@app.route('/api/v1/register', methods=['POST'])
def register_node():
    """Registers a new hardware node in the system database."""
    data = request.json
    if not data or 'id' not in data:
        return jsonify({"success": False, "message": "Missing ID"}), 400
        
    new_bin = Bin(
        id=data['id'],
        supervisor=data.get('supervisor', 'Field Officer'),
        lat=data.get('lat', 0.0),
        lon=data.get('lon', 0.0)
    )
    db.session.merge(new_bin) 
    db.session.commit()
    return jsonify({"success": True})

@app.route('/api/v1/update', methods=['POST'])
def hardware_uplink():
    """Endpoint for hardware to push real-time telemetry."""
    data = request.json
    if not data:
        return jsonify({"success": False}), 400

    bin_id = data.get('bin_id', 'BIN-001')
    fill = data.get('fill_percentage', 0)
    status = data.get('status_msg', 'Monitoring')
    lat = data.get('lat', 0.0)
    lon = data.get('lon', 0.0)

    # 1. Permanent Log
    new_log = Telemetry(bin_id=bin_id, fill_level=fill, status_msg=status)
    db.session.add(new_log)
    db.session.commit()

    # 2. Broadcast to UI
    socketio.emit('update', {
        "bin_id": bin_id,
        "fill_percentage": fill,
        "status_msg": status,
        "lat": lat,
        "lon": lon
    })

    return jsonify({"success": True, "server_time": str(datetime.now())}), 200

# --- 4. EXECUTION ---
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)