#!/usr/bin/env python3
"""
server.py - Eigenständiger Entwicklungs- & Testserver für LeprendiX Companion
Startet einen leichten HTTP-Server für das Companion-Verzeichnis auf Port 5050 (oder beliebig).
"""

import http.server
import socketserver
import os
import sys
import webbrowser
from urllib.parse import urlsplit

PORT = 5050
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def translate_path(self, path):
        if urlsplit(path).path == '/logo.png':
            return os.path.join(os.path.dirname(DIRECTORY), 'logo.png')
        return super().translate_path(path)

    def end_headers(self):
        # Cache deaktivieren während Entwicklung
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

def run_server(port=PORT, open_browser=True):
    os.chdir(DIRECTORY)
    with socketserver.TCPServer(("", port), Handler) as httpd:
        url = f"http://localhost:{port}/index.html"
        print("=" * 60)
        print(f"LeprendiX Companion Web App läuft unter:")
        print(f"  {url}")
        print("=" * 60)
        if open_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer beendet.")

if __name__ == '__main__':
    port = PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port)
