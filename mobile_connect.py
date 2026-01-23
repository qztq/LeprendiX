import threading
import socket
import qrcode
import os
import secrets
import logging
from flask import Flask, request, jsonify
import json

class MobileServer:
    def __init__(self, callback_function, status_callback=None):
        self.app = Flask(__name__)
        self.callback = callback_function
        self.status_callback = status_callback
        self.token = secrets.token_hex(16)
        self.port = 5000
        self.host_ip = self.get_local_ip()
        self.server_thread = None
        self.running = False
        self.scan_requested = False
        
        # Routes
        self.app.add_url_rule('/upload', 'upload', self.handle_upload, methods=['POST'])
        self.app.add_url_rule('/verify', 'verify', self.handle_verify, methods=['POST'])
        self.app.add_url_rule('/status', 'status', self.handle_status, methods=['GET'])

    def get_local_ip(self):
        """Determines the local network IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Connect to a public DNS server to determine outgoing interface
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def start(self):
        """Starts the Flask server in a background thread."""
        if not self.running:
            self.running = True
            self.server_thread = threading.Thread(target=self._run_flask, daemon=True)
            self.server_thread.start()
            logging.info(f"Mobile Server started on {self.host_ip}:{self.port}")

    def _run_flask(self):
        # Suppress standard Flask logging to keep console clean
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        # Run on 0.0.0.0 to be accessible from the network
        self.app.run(host='0.0.0.0', port=self.port, use_reloader=False)

    def get_qr_image(self):
        """Generates a QR code containing IP, Port, and Session Token."""
        # Format: IP:PORT|TOKEN
        data = f"{self.host_ip}:{self.port}|{self.token}"
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        return img

    def handle_verify(self):
        """Endpoint for the app to verify the QR code token."""
        try:
            req_data = request.json
            req_token = req_data.get('token')
            if req_token == self.token:
                return jsonify({"status": "ok", "message": "Connected to LeprendiX"})
            return jsonify({"status": "error", "message": "Invalid Token"}), 403
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    def handle_status(self):
        """Endpoint for mobile app to check status/commands."""
        token = request.args.get('token')
        if token != self.token:
             logging.warning(f"Unauthorized status check. Received: {token}")
             return jsonify({"status": "error", "message": "Unauthorized"}), 403
        
        response_data = {"scan_requested": self.scan_requested}
        if self.scan_requested:
            logging.info("Mobile app polled status: Sending scan request!")
            self.scan_requested = False # Reset after reading
            
        response = jsonify(response_data)
        # Prevent caching to ensure the app always gets the latest status
        response.headers.add('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        return response

    def trigger_scan(self):
        logging.info("Scan triggered from GUI. Waiting for mobile app to poll...")
        self.scan_requested = True

    def handle_upload(self):
        """Endpoint to receive the scanned data from the mobile app."""
        if 'token' not in request.form or request.form['token'] != self.token:
            return jsonify({"status": "error", "message": "Unauthorized"}), 403

        if 'data' not in request.form:
            return jsonify({"status": "error", "message": "No data part in form"}), 400

        if self.status_callback:
            self.status_callback("Daten empfangen. Verarbeite...")

        try:
            # The data is a JSON string in a form field
            json_data_str = request.form['data']
            scanned_data = json.loads(json_data_str)

            # Map the received keys to the keys expected by the GUI
            gui_data = {
                "Anrede": scanned_data.get("anrede"),
                "Vorname": scanned_data.get("vorname"),
                "Nachname": scanned_data.get("nachname"),
                "Versicherungsnummer": scanned_data.get("vsnr"),
                "Diagnose": scanned_data.get("diagnose"),
                "PLZ": scanned_data.get("plz"),
                "Ort": scanned_data.get("ort")
            }

            # Splitting street and house number from "strasse"
            street_full = scanned_data.get("strasse", "")
            last_space_index = street_full.rfind(' ')
            if last_space_index != -1:
                street = street_full[:last_space_index].strip()
                housenumber = street_full[last_space_index+1:].strip()
                # A simple check if the last part is a number or contains a number
                if any(char.isdigit() for char in housenumber):
                    gui_data["Straße"] = street
                    gui_data["Hausnummer"] = housenumber
                else: # if no number, it's all street
                    gui_data["Straße"] = street_full
                    gui_data["Hausnummer"] = ""
            else:
                gui_data["Straße"] = street_full
                gui_data["Hausnummer"] = ""

            # Notify GUI via callback
            if self.callback:
                self.callback(gui_data)

            return jsonify({"status": "success", "data": gui_data})
        except json.JSONDecodeError:
            logging.error(f"Invalid JSON received: {request.form.get('data')}")
            return jsonify({"status": "error", "message": "Invalid JSON in data part"}), 400
        except Exception as e:
            logging.error(f"Error processing scan data: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
