import os
import sys
import shutil
import requests
import zipfile
import tempfile
import hashlib
import subprocess
from tkinter import Tk, Button, Label, messagebox

# ----------------------------------------------------------------------
# KONFIGURATION
# ----------------------------------------------------------------------
DB_FILE_TO_PROTECT = "patienten.db"
REPO_OWNER = "qztq"
REPO_NAME = "LeprendiX"
RELEASE_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"

VERSION_FILE = "version.txt"


# ----------------------------------------------------------------------
# VERSION MANAGEMENT
# ----------------------------------------------------------------------
def get_current_version():
    if not os.path.exists(VERSION_FILE):
        return "0.0.0"
    try:
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except:
        return "0.0.0"


def update_current_version(v):
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(v)


# ----------------------------------------------------------------------
# TOKEN
# ----------------------------------------------------------------------
def get_token():
    """
    Token wird NICHT in den Code geschrieben.
    Du setzt ihn per:
      setx LEPRENDIX_TOKEN "ghp_..."
    """
    tok = os.environ.get("LEPRENDIX_TOKEN")
    if not tok:
        return None
    return tok.strip()


# ----------------------------------------------------------------------
# HASH CHECK
# ----------------------------------------------------------------------
def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ----------------------------------------------------------------------
# UPDATE CHECK
# ----------------------------------------------------------------------
def check_for_updates():
    token = get_token()
    if not token:
        messagebox.showwarning("Updater", "Kein GitHub Token gesetzt.\nBitte LEPRENDIX_TOKEN anlegen.")
        return

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    try:
        print("Checking:", RELEASE_API_URL)
        r = requests.get(RELEASE_API_URL, headers=headers, timeout=15)

        if r.status_code == 404:
            messagebox.showinfo("Updater",
                                "Release nicht gefunden oder Repo privat.\nToken vermutlich ohne Berechtigung.")
            return

        r.raise_for_status()
        data = r.json()

        latest = data.get("tag_name")
        if not latest:
            messagebox.showinfo("Updater", "Release hat keinen tag_name.")
            return

        current = get_current_version()
        print(f"Aktuell: {current} | Latest: {latest}")

        if latest <= current:
            messagebox.showinfo("Updater", "Keine neuere Version verfügbar.")
            return

        # ZIP Asset suchen
        assets = data.get("assets", [])
        zip_asset = None
        for a in assets:
            if a.get("name", "").lower().endswith(".zip"):
                zip_asset = a
                break

        if not zip_asset:
            messagebox.showerror("Updater", "Release hat kein ZIP-Asset.")
            return

        if not messagebox.askyesno(
            "Update verfügbar",
            f"Version {latest} gefunden.\nAktuell: {current}\n\nJetzt aktualisieren?"
        ):
            return

        url = zip_asset.get("browser_download_url")
        digest = zip_asset.get("digest")  # optional

        download_and_install(url, headers, latest, digest)

    except Exception as e:
        messagebox.showerror("Updater Fehler", str(e))


# ----------------------------------------------------------------------
# DOWNLOAD + INSTALL
# ----------------------------------------------------------------------
def download_and_install(url, headers, new_version, digest=None):
    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    temp_zip.close()

    try:
        # --- DOWNLOAD ---
        with requests.get(url, headers=headers, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(temp_zip.name, "wb") as f:
                for chunk in r.iter_content(8192):
                    if chunk:
                        f.write(chunk)

        # --- HASH CHECK ---
        if digest and digest.startswith("sha256:"):
            expected = digest.split("sha256:", 1)[1].strip()
            actual = sha256_of(temp_zip.name)
            print("Expected:", expected)
            print("Actual:  ", actual)
            if actual != expected:
                os.remove(temp_zip.name)
                messagebox.showerror("Updater", "SHA256 stimmt nicht!\nUpdate abgebrochen.")
                return

        # --- ENTZIP ---
        tmpdir = tempfile.mkdtemp(prefix="update_")
        with zipfile.ZipFile(temp_zip.name, "r") as zf:
            zf.extractall(tmpdir)

        # --- INSTALLATION ---
        cwd = os.getcwd()
        backup = tempfile.mkdtemp(prefix="backup_")

        try:
            for root, dirs, files in os.walk(tmpdir):
                rel_root = os.path.relpath(root, tmpdir)

                for file in files:
                    source = os.path.join(root, file)

                    if rel_root == ".":
                        target_rel = file
                    else:
                        target_rel = os.path.join(rel_root, file)

                    target = os.path.join(cwd, target_rel)

                    # DB NIE überschreiben!
                    if os.path.basename(target).lower() == DB_FILE_TO_PROTECT.lower():
                        print("Skipping DB:", target)
                        continue

                    os.makedirs(os.path.dirname(target), exist_ok=True)

                    # Backup falls existiert
                    if os.path.exists(target):
                        bkp_path = os.path.join(backup, target_rel)
                        os.makedirs(os.path.dirname(bkp_path), exist_ok=True)
                        shutil.copy2(target, bkp_path)

                    shutil.copy2(source, target)
                    print("Updated:", target)

        except Exception as e:
            # Restore
            for root, dirs, files in os.walk(backup):
                for file in files:
                    src = os.path.join(root, file)
                    rel = os.path.relpath(src, backup)
                    dst = os.path.join(cwd, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)

            messagebox.showerror("Update Fehler",
                                 f"Beim Installieren ist ein Fehler aufgetreten.\n"
                                 f"Backup wurde wiederhergestellt.\n\n{e}")
            return

        update_current_version(new_version)

        messagebox.showinfo("Update",
                            "Update erfolgreich installiert!\nDas Programm wird jetzt neu gestartet.")

        restart_app()

    finally:
        try:
            os.remove(temp_zip.name)
        except:
            pass


# ----------------------------------------------------------------------
# NEUSTART
# ----------------------------------------------------------------------
def restart_app():
    python = sys.executable
    os.execl(python, python, *sys.argv)


# ----------------------------------------------------------------------
# START VON START.PY
# ----------------------------------------------------------------------
def start_app():
    if not os.path.exists("start.py"):
        messagebox.showerror("Fehler", "start.py wurde nicht gefunden!")
        return

    try:
        subprocess.Popen([sys.executable, "start.py"])
    except Exception as e:
        messagebox.showerror("Start-Fehler", str(e))


# ----------------------------------------------------------------------
# GUI
# ----------------------------------------------------------------------
def main():
    root = Tk()
    root.title("LeprendiX Launcher")
    root.geometry("360x200")

    Label(root, text=f"LeprendiX\nVersion {get_current_version()}",
          font=("Arial", 14)).pack(pady=15)

    Button(root, text="Programm starten", width=18, height=2,
           command=start_app).pack(pady=5)

    Button(root, text="Nach Updates suchen", width=18, height=2,
           command=check_for_updates).pack(pady=5)

    root.mainloop()


if __name__ == "__main__":
    main()
