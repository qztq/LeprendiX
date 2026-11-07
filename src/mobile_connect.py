import threading
import socket
import qrcode
import os
import sys
import secrets
import logging
import datetime
import base64
import json
import sqlite3
import re
from flask import Flask, request, jsonify, send_from_directory
from src.config_loader import CONFIG
from src.companion_contracts import get_contract_directory, load_contracts
from src.project_paths import get_app_directory


def _runtime_roots():
    """Gibt mögliche Basisverzeichnisse für Quellcode und PyInstaller-Bundles zurück."""
    roots = []
    executable_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else None
    bundle_dir = getattr(sys, '_MEIPASS', None)
    source_dir = get_app_directory()

    for path in (executable_dir, bundle_dir, source_dir):
        if path:
            normalized = os.path.abspath(path)
            if normalized not in roots:
                roots.append(normalized)
    return roots


def _resolve_companion_dir():
    """Findet Companion-Dateien sowohl im Ordner als auch im flachen PyInstaller-Bundle."""
    roots = _runtime_roots()
    for root in roots:
        for candidate in (os.path.join(root, 'Companion'), root):
            if os.path.isfile(os.path.join(candidate, 'index.html')):
                return candidate
    return os.path.join(roots[0], 'Companion') if roots else os.path.join(
        get_app_directory(), 'Companion'
    )


class MobileServer:
    def __init__(self, callback_function, status_callback=None, batch_callback=None, db_path=None):
        self.app = Flask(__name__)
        self.callback = callback_function
        self.status_callback = status_callback
        self.batch_callback = batch_callback
        self.db_path = db_path or os.path.join(
            get_app_directory(), 'patienten.db'
        )
        self.connection_callback = None
        self.cancel_callback = None
        self.token = secrets.token_hex(16)
        self.port = 5000
        self.host_ip = self.get_local_ip()
        self.server_thread = None
        self.running = False
        self.scan_requested = False
        self.ping_requested = False

        self.companion_dir = _resolve_companion_dir()
        
        # CORS & Headers
        @self.app.after_request
        def add_cors_headers(response):
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            return response

        # Routes - Companion Web App
        self.app.add_url_rule('/', 'companion_index', self.serve_companion_index, methods=['GET'])
        self.app.add_url_rule('/logo.png', 'companion_logo', self.serve_companion_logo, methods=['GET'])
        self.app.add_url_rule('/<path:filename>', 'companion_static', self.serve_companion_file, methods=['GET'])

        # Routes - API
        self.app.add_url_rule('/upload', 'upload', self.handle_upload, methods=['POST', 'OPTIONS'])
        self.app.add_url_rule('/sync_batch', 'sync_batch', self.handle_sync_batch, methods=['POST', 'OPTIONS'])
        self.app.add_url_rule('/calculate_distance', 'calculate_distance', self.handle_calculate_distance, methods=['POST', 'OPTIONS'])
        self.app.add_url_rule('/verify', 'verify', self.handle_verify, methods=['POST', 'OPTIONS'])
        self.app.add_url_rule('/pong', 'pong', self.handle_pong, methods=['POST', 'OPTIONS'])
        self.app.add_url_rule('/status', 'status', self.handle_status, methods=['GET', 'OPTIONS'])
        self.app.add_url_rule('/report_status', 'report_status', self.handle_report_status, methods=['POST', 'OPTIONS'])
        self.app.add_url_rule('/contracts', 'contracts', self.handle_contracts, methods=['GET', 'OPTIONS'])
        self.app.add_url_rule('/app-version', 'app_version', self.handle_app_version, methods=['GET'])

    def serve_companion_index(self):
        """Liefert die Hauptseite der Companion-App aus."""
        index_path = os.path.join(self.companion_dir, 'index.html')
        if os.path.isfile(index_path):
            return send_from_directory(self.companion_dir, 'index.html')
        searched = ', '.join(
            os.path.join(root, 'Companion') for root in _runtime_roots()
        )
        return (
            "LeprendiX Companion index.html nicht gefunden. "
            f"Geprüfte Bundle-Ordner: {searched}",
            404
        )

    def serve_companion_logo(self):
        """Liefert das gemeinsame Anwendungslogo an die Companion-App aus."""
        for root in _runtime_roots():
            logo_path = os.path.join(root, 'assets', 'logo.png')
            if os.path.isfile(logo_path):
                return send_from_directory(os.path.join(root, 'assets'), 'logo.png')
        return "LeprendiX logo.png nicht gefunden.", 404

    def serve_companion_file(self, filename):
        """Liefert statische Dateien (CSS, JS, Res) der Companion-App aus."""
        normalized_filename = filename.replace("\\", "/")
        if normalized_filename == "app-version.json":
            return self.handle_app_version()
        if normalized_filename == "res" or normalized_filename.startswith("res/"):
            return "Verträge werden nur über die authentifizierte Verbindung geladen.", 404

        safe_path = os.path.normpath(os.path.join(self.companion_dir, filename))
        if os.path.commonpath([self.companion_dir, safe_path]) == self.companion_dir and os.path.exists(safe_path):
            return send_from_directory(self.companion_dir, filename)
        return "Datei nicht gefunden", 404

    def handle_contracts(self):
        if request.method == 'OPTIONS':
            return jsonify({"status": "ok"})
        authorization = request.headers.get("Authorization", "")
        supplied_token = (
            authorization[len("Bearer "):].strip()
            if authorization.startswith("Bearer ")
            else ""
        )
        if supplied_token != self.token:
            return jsonify({"status": "error", "message": "Unauthorized"}), 403

        contract_dir = get_contract_directory(CONFIG.get("COMPANION_CONTRACTS_DIR"))
        try:
            contracts = load_contracts(contract_dir)
        except (OSError, ValueError) as error:
            logging.exception("Companion-Verträge konnten nicht geladen werden.")
            return jsonify({
                "status": "error",
                "message": f"Verträge konnten nicht geladen werden: {error}",
            }), 500
        return jsonify({"status": "ok", "contracts": contracts})

    @staticmethod
    def handle_app_version():
        for root in _runtime_roots():
            version_path = os.path.join(root, "version.txt")
            if os.path.isfile(version_path):
                with open(version_path, "r", encoding="utf-8") as file:
                    return jsonify({"version": file.read().strip()})
        return jsonify({"error": "version.txt nicht gefunden"}), 404

    def set_connection_callback(self, callback):
        self.connection_callback = callback

    def set_cancel_callback(self, callback):
        self.cancel_callback = callback

    def get_local_ip(self):
        """Determines the local network IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
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
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        self.app.run(host='0.0.0.0', port=self.port, use_reloader=False)

    def get_qr_image(self):
        """Generates a QR code containing direct URL to Companion web app."""
        url = f"http://{self.host_ip}:{self.port}/?token={self.token}"
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        return img

    def handle_calculate_distance(self):
        """Berechnet die Entfernung von der Praxisadresse zur Patientenadresse."""
        if request.method == 'OPTIONS':
            return jsonify({"status": "ok"})
        try:
            req_data = request.get_json(force=True, silent=True) or {}
            patient_address = req_data.get('address')
            if not patient_address:
                return jsonify({"status": "error", "message": "Adresse fehlt"}), 400

            fixed_address = "Triesterstraße 10/4, 2351 Wiener Neudorf"
            config_path = os.path.join(get_app_directory(), 'config.json')
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        cfg = json.load(f)
                        if cfg.get('FIXED_ADDRESS'):
                            fixed_address = cfg['FIXED_ADDRESS']
                except Exception:
                    pass

            from geopy.geocoders import Nominatim
            import requests

            geolocator = Nominatim(user_agent="leprendix-companion-dist-calc")
            loc1 = geolocator.geocode(f"{patient_address}, Austria", timeout=6)
            loc2 = geolocator.geocode(f"{fixed_address}, Austria", timeout=6)

            if loc1 and loc2:
                osrm_url = f"http://router.project-osrm.org/route/v1/driving/{loc1.longitude},{loc1.latitude};{loc2.longitude},{loc2.latitude}"
                resp = requests.get(osrm_url, timeout=6)
                if resp.ok:
                    data = resp.json()
                    if data.get('code') == 'Ok':
                        dist_km = round(data['routes'][0]['distance'] / 1000.0, 1)
                        suggested_km = round(dist_km * 2, 2)
                        return jsonify({
                            "status": "ok",
                            "distance_km": dist_km,
                            "fixed_address": fixed_address,
                            "suggested_km_geld": suggested_km
                        })

            return jsonify({
                "status": "warning",
                "message": "Route konnte nicht exakt ermittelt werden",
                "distance_km": 0.0,
                "suggested_km_geld": 0.0,
                "fixed_address": fixed_address
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e),
                "distance_km": 0.0,
                "suggested_km_geld": 0.0
            })

    def handle_verify(self):
        """Endpoint for the app to verify the QR code token."""
        if request.method == 'OPTIONS':
            return jsonify({"status": "ok"})
        try:
            req_data = request.get_json(force=True, silent=True) or {}
            req_token = req_data.get('token') or request.form.get('token')
            if req_token == self.token:
                return jsonify({"status": "ok", "message": "Connected to LeprendiX"})
            return jsonify({"status": "error", "message": "Invalid Token"}), 403
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    def handle_pong(self):
        """Endpoint for client to send pong and establish connection."""
        if request.method == 'OPTIONS':
            return jsonify({"status": "ok"})
        try:
            req_data = request.get_json(force=True, silent=True) or {}
            req_token = req_data.get('token') or request.form.get('token')
            status = req_data.get('status') or request.form.get('status')
            
            if req_token == self.token:
                if status == 'pong':
                    logging.info("Pong received from client.")
                    if self.connection_callback:
                        self.connection_callback()
                    return jsonify({"status": "ok", "message": "Connected"})
                elif status == 'cancelled':
                    logging.info("Cancellation received from client.")
                    if self.cancel_callback:
                        self.cancel_callback()
                    return jsonify({"status": "ok", "message": "Cancelled"})
            return jsonify({"status": "error", "message": "Invalid Token or Status"}), 403
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    def handle_report_status(self):
        """Endpoint for client to report status updates (e.g. cancellation)."""
        if request.method == 'OPTIONS':
            return jsonify({"status": "ok"})
        try:
            req_data = request.get_json(force=True, silent=True) or {}
            req_token = req_data.get('token') or request.form.get('token')
            status = req_data.get('status') or request.form.get('status')
            
            if req_token == self.token:
                if status == 'cancelled':
                    logging.info("Cancellation received via report_status.")
                    if self.cancel_callback:
                        self.cancel_callback()
                    return jsonify({"status": "ok", "message": "Cancelled"})
                return jsonify({"status": "ok", "message": "Status ignored"})
            return jsonify({"status": "error", "message": "Invalid Token"}), 403
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    def handle_status(self):
        """Endpoint for mobile app to check status/commands."""
        if request.method == 'OPTIONS':
            return jsonify({"status": "ok"})
        token = request.args.get('token')
        if token != self.token:
            logging.warning(f"Unauthorized status check. Received: {token}")
            return jsonify({"status": "error", "message": "Unauthorized"}), 403
        
        status_msg = "ping"
        if self.ping_requested:
            logging.info("PINGPONG: Sending PINGPONG to client.")
            status_msg = "PINGPONG"
            self.ping_requested = False
            self.scan_requested = True
            logging.info("PINGPONG: Automatically triggering scan request.")

        response_data = {
            "scan_requested": self.scan_requested,
            "status": status_msg
        }
        if self.scan_requested:
            logging.info("Mobile app polled status: Sending scan request!")
            self.scan_requested = False
            
        response = jsonify(response_data)
        response.headers.add('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        return response

    def trigger_scan(self):
        logging.info("Scan triggered from GUI. Waiting for mobile app to poll...")
        self.scan_requested = True

    def send_ping(self):
        """Sets a flag to send PINGPONG status on next poll."""
        logging.info("PINGPONG: send_ping triggered.")
        self.ping_requested = True

    def _save_signed_contracts(self, gui_data, contracts_package, signature_b64):
        """Speichert unterzeichnete DSGVO-Verträge und die Unterschrift als Bild."""
        try:
            signatures_dir = os.path.join(self.companion_dir, 'signatures')
            os.makedirs(signatures_dir, exist_ok=True)

            timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            clean_nachname = re.sub(r'[^a-zA-Z0-9_\-äöüÄÖÜß]', '_', gui_data.get("Nachname") or "Patient")
            clean_vorname = re.sub(r'[^a-zA-Z0-9_\-äöüÄÖÜß]', '_', gui_data.get("Vorname") or "")
            base_filename = f"{timestamp_str}_{clean_nachname}_{clean_vorname}".strip("_")

            # 1. Signatur-PNG speichern
            if signature_b64 and "base64," in signature_b64:
                _, encoded = signature_b64.split("base64,", 1)
                img_data = base64.b64decode(encoded)
                sig_path = os.path.join(signatures_dir, f"{base_filename}_signature.png")
                with open(sig_path, "wb") as f:
                    f.write(img_data)
                logging.info(f"DSGVO Signatur als PNG archiviert: {sig_path}")

            # 2. Vertragsprotokoll als JSON sichern
            if contracts_package:
                contract_path = os.path.join(signatures_dir, f"{base_filename}_vertrag.json")
                with open(contract_path, "w", encoding="utf-8") as f:
                    json.dump(contracts_package, f, ensure_ascii=False, indent=2)
                logging.info(f"DSGVO Vertragsprotokoll archiviert: {contract_path}")
        except Exception as e:
            logging.error(f"Fehler beim Archivieren der DSGVO-Signatur: {e}")

    def handle_upload(self):
        """Endpoint to receive the scanned data from the mobile/companion app (Einzelübertragung)."""
        if request.method == 'OPTIONS':
            return jsonify({"status": "ok"})

        token = None
        raw_data = None

        if request.form and 'token' in request.form:
            token = request.form['token']
            raw_data = request.form.get('data')
        elif request.is_json:
            req_json = request.get_json(silent=True) or {}
            token = req_json.get('token')
            raw_data = req_json.get('data')

        if token != self.token:
            return jsonify({"status": "error", "message": "Unauthorized"}), 403

        if not raw_data:
            return jsonify({"status": "error", "message": "No data part in request"}), 400

        if self.status_callback:
            self.status_callback("Daten empfangen. Verarbeite...")

        try:
            if isinstance(raw_data, str):
                scanned_data = json.loads(raw_data)
            else:
                scanned_data = raw_data

            anrede = (scanned_data.get("anrede") or "Herr/Frau").strip()
            titel = scanned_data.get("titel")
            if titel:
                if isinstance(titel, list):
                    titel = " ".join(titel).strip()
                titel = str(titel).strip()
                if titel and not anrede.endswith(titel):
                    anrede = f"{anrede} {titel}".strip()

            vorname = (scanned_data.get("vorname") or "").strip()
            if titel and vorname.startswith(titel):
                vorname = vorname[len(titel):].strip()

            km_geld = 0.0
            try:
                km_geld = float(scanned_data.get("kilometergeld", 0.0) or 0.0)
            except (ValueError, TypeError):
                km_geld = 0.0

            gui_data = {
                "Anrede": anrede,
                "Vorname": vorname,
                "Nachname": scanned_data.get("nachname"),
                "Versicherungsnummer": scanned_data.get("vsnr"),
                "Diagnose": scanned_data.get("diagnose"),
                "PLZ": scanned_data.get("plz"),
                "Ort": scanned_data.get("ort"),
                "Adresszusatz": scanned_data.get("adresszusatz", ""),
                "Kilometergeld": km_geld
            }

            if scanned_data.get("hausnummer"):
                gui_data["Straße"] = scanned_data.get("strasse", "").strip()
                gui_data["Hausnummer"] = scanned_data.get("hausnummer", "").strip()
            else:
                street_full = scanned_data.get("strasse", "")
                last_space_index = street_full.rfind(' ')
                if last_space_index != -1:
                    street = street_full[:last_space_index].strip()
                    housenumber = street_full[last_space_index+1:].strip()
                    if any(char.isdigit() for char in housenumber):
                        gui_data["Straße"] = street
                        gui_data["Hausnummer"] = housenumber
                    else:
                        gui_data["Straße"] = street_full
                        gui_data["Hausnummer"] = ""
                else:
                    gui_data["Straße"] = street_full
                    gui_data["Hausnummer"] = ""

            contracts_pkg = scanned_data.get("contracts")
            signature_b64 = scanned_data.get("signature")
            if contracts_pkg or signature_b64:
                self._save_signed_contracts(gui_data, contracts_pkg, signature_b64)

            if self.callback:
                self.callback(gui_data)

            return jsonify({"status": "success", "data": gui_data})
        except json.JSONDecodeError:
            logging.error(f"Invalid JSON received: {raw_data}")
            return jsonify({"status": "error", "message": "Invalid JSON in data part"}), 400
        except Exception as e:
            logging.error(f"Error processing scan data: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    def handle_sync_batch(self):
        """Endpoint to receive batch of offline-collected patient records at the end of the month."""
        if request.method == 'OPTIONS':
            return jsonify({"status": "ok"})

        req_json = request.get_json(silent=True)
        if not isinstance(req_json, dict):
            return jsonify({"status": "error", "message": "Invalid JSON request"}), 400

        token = req_json.get('token')
        records = req_json.get('records')

        if token != self.token:
            return jsonify({"status": "error", "message": "Unauthorized"}), 403

        if records is None:
            return jsonify({"status": "ok", "message": "No records to sync", "synced_ids": []})
        if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
            return jsonify({"status": "error", "message": "Records must be a list of objects"}), 400
        if not records:
            return jsonify({"status": "ok", "message": "No records to sync", "synced_ids": []})
        if not self.batch_callback:
            logging.error("Batch-Sync abgelehnt: Kein Abschluss-Callback für den Stammdaten-Assistenten konfiguriert.")
            return jsonify({
                "status": "error",
                "message": "Der Stammdaten-Assistent ist nicht verfügbar. Der Sync wurde nicht bestätigt."
            }), 503

        for record in records:
            patient = record.get('patient', record)
            if not isinstance(record.get('id'), str) or not record['id'].strip():
                return jsonify({"status": "error", "message": "Every record needs a non-empty id"}), 400
            if not isinstance(patient, dict):
                return jsonify({"status": "error", "message": "Every record needs patient data"}), 400

        if self.status_callback:
            self.status_callback(f"Synchronisiere {len(records)} Datensätze vom Tablet...")

        synced_ids = []
        imported_count = 0
        updated_count = 0
        reactivated_count = 0
        processed_patients = []

        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(patienten)")
            patient_columns = {column[1] for column in cursor.fetchall()}
            if 'krankenkasse' not in patient_columns:
                cursor.execute("ALTER TABLE patienten ADD COLUMN krankenkasse TEXT DEFAULT ''")

            for record in records:
                record_id = record['id'].strip()
                patient = record.get('patient', record)

                anrede = (patient.get('anrede') or 'Herr/Frau').strip()
                titel = patient.get('titel', '')
                if isinstance(titel, list):
                    titel = " ".join(titel).strip()
                titel = str(titel).strip()
                if titel and not anrede.endswith(titel):
                    anrede = f"{anrede} {titel}".strip()

                vorname = (patient.get('vorname') or '').strip()
                if titel and vorname.startswith(titel):
                    vorname = vorname[len(titel):].strip()

                nachname = (patient.get('nachname') or '').strip()
                vsnr = (patient.get('vsnr') or '').strip()
                krankenkasse = (patient.get('krankenkasse') or '').strip()
                diagnose = patient.get('diagnose') or 'Z71'
                plz = (patient.get('plz') or '').strip()
                ort = (patient.get('ort') or '').strip()
                strasse = (patient.get('strasse') or '').strip()
                hausnummer = (patient.get('hausnummer') or '').strip()
                adresszusatz = (patient.get('adresszusatz') or '').strip()

                try:
                    km_geld = float(patient.get('kilometergeld', 0.0) or 0.0)
                except (ValueError, TypeError):
                    km_geld = 0.0

                contracts_package = record.get('contracts')
                signature = record.get('signature')
                if not signature and isinstance(contracts_package, dict):
                    signature = contracts_package.get('signatureImage')
                if contracts_package or signature:
                    self._save_signed_contracts(
                        {"Vorname": vorname, "Nachname": nachname},
                        contracts_package,
                        signature
                    )

                existing_patient = None
                if vsnr:
                    cursor.execute(
                        """
                        SELECT id, is_archived FROM patienten
                        WHERE versicherungsnummer = ?
                        ORDER BY CASE WHEN COALESCE(is_archived, 0) = 0 THEN 0 ELSE 1 END, id
                        LIMIT 1
                        """,
                        (vsnr,)
                    )
                    existing_patient = cursor.fetchone()

                if not existing_patient:
                    cursor.execute(
                        """
                        SELECT id, is_archived FROM patienten
                        WHERE nachname = ? AND vorname = ? AND plz = ?
                        ORDER BY CASE WHEN COALESCE(is_archived, 0) = 0 THEN 0 ELSE 1 END, id
                        LIMIT 1
                        """,
                        (nachname, vorname, plz)
                    )
                    existing_patient = cursor.fetchone()

                if not existing_patient:
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO patienten (
                            vorname, nachname, strasse, hausnummer, adresszusatz, plz, ort,
                            anrede, versicherungsnummer, diagnose, krankenkasse, kilometergeld,
                            last_selected_kurznamen, invoiced_since_reset
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', 0)
                        """,
                        (
                            vorname, nachname, strasse, hausnummer, adresszusatz, plz,
                            ort, anrede, vsnr, diagnose, krankenkasse, km_geld
                        )
                    )
                    if cursor.rowcount == 1:
                        patient_id = cursor.lastrowid
                        imported_count += 1
                    else:
                        cursor.execute(
                            """
                            SELECT id, is_archived FROM patienten
                            WHERE vorname = ? COLLATE NOCASE
                              AND nachname = ? COLLATE NOCASE
                              AND plz = ? COLLATE NOCASE
                            ORDER BY CASE WHEN COALESCE(is_archived, 0) = 0 THEN 0 ELSE 1 END, id
                            LIMIT 1
                            """,
                            (vorname, nachname, plz)
                        )
                        existing_patient = cursor.fetchone()
                        if not existing_patient:
                            raise sqlite3.IntegrityError(
                                "Patient konnte nach einem INSERT-Konflikt nicht anhand "
                                "von Vorname, Nachname und PLZ gefunden werden."
                            )

                if existing_patient:
                    patient_id = existing_patient[0]
                    was_archived = bool(existing_patient[1])
                    cursor.execute(
                        """
                        UPDATE patienten
                        SET vorname = COALESCE(NULLIF(?, ''), vorname),
                            nachname = COALESCE(NULLIF(?, ''), nachname),
                            strasse = COALESCE(NULLIF(?, ''), strasse),
                            hausnummer = COALESCE(NULLIF(?, ''), hausnummer),
                            adresszusatz = COALESCE(NULLIF(?, ''), adresszusatz),
                            plz = COALESCE(NULLIF(?, ''), plz),
                            ort = COALESCE(NULLIF(?, ''), ort),
                            anrede = COALESCE(NULLIF(?, ''), anrede),
                            versicherungsnummer = COALESCE(NULLIF(?, ''), versicherungsnummer),
                            diagnose = COALESCE(NULLIF(?, ''), diagnose),
                            krankenkasse = COALESCE(NULLIF(?, ''), krankenkasse),
                            kilometergeld = CASE WHEN ? > 0 THEN ? ELSE kilometergeld END,
                            is_archived = 0
                        WHERE id = ?
                        """,
                        (
                            vorname, nachname, strasse, hausnummer, adresszusatz,
                            plz, ort, anrede, vsnr,
                            diagnose, krankenkasse, km_geld, km_geld, patient_id
                        )
                    )
                    updated_count += 1
                    if was_archived:
                        reactivated_count += 1

                processed_patients.append({
                    "id": record_id,
                    "db_id": patient_id,
                    "anrede": anrede,
                    "vorname": vorname,
                    "nachname": nachname,
                    "name": f"{anrede} {vorname} {nachname}".strip(),
                    "vsnr": vsnr,
                    "krankenkasse": krankenkasse,
                    "ort": f"{plz} {ort}".strip(),
                    "adresse": f"{strasse} {hausnummer}".strip(),
                    "kilometergeld": km_geld,
                    "diagnose": diagnose
                })

            conn.commit()

            callback_completed = self.batch_callback(processed_patients)
            if callback_completed is not True:
                if self.status_callback:
                    self.status_callback(
                        "Sync nicht bestätigt: Stammdaten-Assistent wurde nicht vollständig abgeschlossen."
                    )
                return jsonify({
                    "status": "error",
                    "message": (
                        "Der Stammdaten-Assistent wurde nicht vollständig abgeschlossen. "
                        "Die Patienten bleiben am Companion als ausstehend markiert."
                    ),
                    "synced_ids": []
                }), 409

            synced_ids = [patient["id"] for patient in processed_patients]
            if self.status_callback:
                self.status_callback(
                    f"Sync bestätigt: {imported_count} neu importiert, "
                    f"{reactivated_count} archivierte reaktiviert, "
                    f"{updated_count - reactivated_count} aktualisiert."
                )

            return jsonify({
                "status": "success",
                "synced_ids": synced_ids,
                "imported": imported_count,
                "updated": updated_count,
                "reactivated": reactivated_count,
                "patients": processed_patients
            })

        except Exception as e:
            if conn:
                conn.rollback()
            logging.error(f"Error during handle_sync_batch: {e}", exc_info=True)
            return jsonify({"status": "error", "message": str(e), "synced_ids": synced_ids}), 500
        finally:
            if conn:
                conn.close()
