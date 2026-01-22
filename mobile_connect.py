import threading
import socket
import qrcode
import os
import secrets
import logging
from flask import Flask, request, jsonify
from PIL import Image
import requests
import io

# Optional OCR support
try:
    import pytesseract
    # If tesseract is not in PATH, set it here:
    # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logging.warning("pytesseract not installed. OCR functionality will be limited.")

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
             return jsonify({"status": "error", "message": "Unauthorized"}), 403
        
        response = {"scan_requested": self.scan_requested}
        if self.scan_requested:
            self.scan_requested = False # Reset after reading
        return jsonify(response)

    def trigger_scan(self):
        self.scan_requested = True

    def handle_upload(self):
        """Endpoint to receive the scanned image."""
        if 'token' not in request.form or request.form['token'] != self.token:
            return jsonify({"status": "error", "message": "Unauthorized"}), 403
            
        if 'image' not in request.files:
            return jsonify({"status": "error", "message": "No image part"}), 400
            
        file = request.files['image']
        
        if self.status_callback:
            self.status_callback("Bild empfangen. Verarbeite...")

        try:
            image = Image.open(file.stream)
            extracted_data = self.process_image(image)
            
            # Notify GUI via callback (runs in Flask thread)
            if self.callback:
                self.callback(extracted_data)
                
            return jsonify({"status": "success", "data": extracted_data})
        except Exception as e:
            logging.error(f"Error processing scan: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    def process_image(self, image):
        """Performs OCR using OCR.space API (Free) with fallback to local Tesseract."""
        extracted_text = ""
        
        # 1. Try OCR.space API (Free)
        try:
            # Convert image to bytes for upload
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)

            payload = {
                'apikey': 'helloworld', # Free demo key. For production, get a free key at ocr.space
                'language': 'ger',
                'isOverlayRequired': False
            }
            files = {
                'file': ('scan.png', img_byte_arr, 'image/png')
            }
            
            logging.info("Sending image to OCR.space API...")
            response = requests.post('https://api.ocr.space/parse/image', 
                                     files=files, 
                                     data=payload, 
                                     timeout=15)
            
            result = response.json()
            
            if result.get('IsErroredOnProcessing') == False:
                parsed_results = result.get('ParsedResults')
                if parsed_results:
                    extracted_text = parsed_results[0].get('ParsedText', '')
                    logging.info("OCR API success.")
            else:
                logging.warning(f"OCR API Error: {result.get('ErrorMessage')}")
                
        except Exception as e:
            logging.error(f"OCR API Request failed: {e}")

        # 2. Fallback to local Tesseract
        if not extracted_text:
            if OCR_AVAILABLE:
                logging.info("Falling back to local Tesseract OCR...")
                try:
                    extracted_text = pytesseract.image_to_string(image, lang='deu+eng')
                except Exception as e:
                    logging.error(f"Local Tesseract failed: {e}")
            else:
                return {"error": "Kein Text erkannt. (API fehlgeschlagen & Tesseract nicht installiert)"}
        
        if not extracted_text:
             return {"error": "Leeres Ergebnis vom OCR Scan."}

        # 3. Parse Data
        try:
            data = {"raw_text": extracted_text}
            
            # Very basic keyword extraction logic
            lines = extracted_text.split('\n')
            for line in lines:
                clean_line = line.strip()
                if not clean_line: continue
                
                lower_line = clean_line.lower()
                
                # Heuristic parsing (Key: Value)
                if ":" in clean_line:
                    parts = clean_line.split(":", 1)
                    key = parts[0].strip().lower()
                    val = parts[1].strip()

                    if "vorname" in key: data["Vorname"] = val
                    elif "nachname" in key or "name" == key: data["Nachname"] = val
                    elif "diagnose" in key: data["Diagnose"] = val
                    elif "versicherungsnummer" in key or "svnr" in key: data["Versicherungsnummer"] = val
                    elif "plz" in key: data["PLZ"] = val
                    elif "ort" in key: data["Ort"] = val
                    elif "straße" in key or "strasse" in key: data["Straße"] = val
                    elif "hausnummer" in key: data["Hausnummer"] = val
            
            return data
        except Exception as e:
            return {"error": str(e)}
