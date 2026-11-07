import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Companion"
DESTINATION = ROOT / "build" / "companion-web"
PUBLIC_FILES = ("index.html", "manifest.json", "favicon.ico", "sw.js")
PUBLIC_DIRECTORIES = ("css", "js")


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)

    for filename in PUBLIC_FILES:
        source = SOURCE / filename
        if not source.is_file():
            raise FileNotFoundError(f"Required Companion file is missing: {source}")
        shutil.copy2(source, DESTINATION / filename)

    logo = ROOT / "assets" / "logo.png"
    if not logo.is_file():
        raise FileNotFoundError(f"Required application logo is missing: {logo}")
    shutil.copy2(logo, DESTINATION / "logo.png")

    for directory in PUBLIC_DIRECTORIES:
        source = SOURCE / directory
        if not source.is_dir():
            raise FileNotFoundError(f"Required Companion directory is missing: {source}")
        shutil.copytree(source, DESTINATION / directory, dirs_exist_ok=True)

    staged_resources = DESTINATION / "res"
    if staged_resources.is_dir():
        for staged_contract in staged_resources.glob("*.json"):
            if staged_contract.is_file():
                staged_contract.unlink()

    version_path = ROOT / "version.txt"
    if not version_path.is_file():
        raise FileNotFoundError(f"Required application version is missing: {version_path}")
    version = version_path.read_text(encoding="utf-8").strip()
    if not version:
        raise ValueError(f"Application version is empty: {version_path}")
    (DESTINATION / "app-version.json").write_text(
        json.dumps({"version": version}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
