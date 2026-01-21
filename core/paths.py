import sys
import os
import tempfile

def get_project_root():
    """Gets the project root directory."""
    if getattr(sys, 'frozen', False):
        # The .exe is in the root directory
        return os.path.dirname(sys.executable)
    else:
        # Assumes this file is in LeprendiX/leprendix/core/
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

def get_bundled_resource_path(relative_path):
    """Gets path to a bundled resource (e.g., in _MEIPASS). Returns None if not found."""
    if hasattr(sys, '_MEIPASS'):
        # The relative path for assets should be 'assets/file.ext'
        bundled_path = os.path.join(sys._MEIPASS, relative_path)
        if os.path.exists(bundled_path):
            return bundled_path
    return None

# --- Core Paths ---
PROJECT_ROOT = get_project_root()
LEPRENDIX_DIR = os.path.join(PROJECT_ROOT, 'leprendix')

# --- Data Paths (writable) ---
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
DB_PATH = os.path.join(DATA_DIR, 'patienten.db')
CREDENTIALS_PATH = os.path.join(DATA_DIR, 'credentials.dat')
CONFIG_PATH = os.path.join(DATA_DIR, 'config.json')
BACKUPS_DIR = os.path.join(DATA_DIR, 'backups')

# --- Log Path ---
def get_log_dir():
    app_name = "LeprendiX"
    if sys.platform == "win32":
        base_path = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or os.path.expanduser("~")
    else:
        base_path = os.path.join(os.path.expanduser("~"), ".local", "share")
    
    log_dir = os.path.join(base_path, app_name, "logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
        return log_dir
    except Exception:
        return tempfile.gettempdir()

LOG_DIR = get_log_dir()
LOG_FILE = os.path.join(LOG_DIR, "leprendix.log")

# --- Asset Paths (read-only) ---
ASSETS_DIR = os.path.join(LEPRENDIX_DIR, 'assets')
LOGO_PATH = get_bundled_resource_path('assets/logo.png') or os.path.join(ASSETS_DIR, 'logo.png')
TEMPLATE_PATH = get_bundled_resource_path('assets/honorar_vorlage.docx') or os.path.join(ASSETS_DIR, 'honorar_vorlage.docx')
VERSION_PATH = os.path.join(PROJECT_ROOT, 'version.txt')

# --- Ensure data directories exist on startup ---
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)