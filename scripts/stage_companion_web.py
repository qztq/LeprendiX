import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Companion"
DESTINATION = ROOT / "build" / "companion-web"
PUBLIC_FILES = ("index.html", "manifest.json", "favicon.ico", "sw.js")
PUBLIC_DIRECTORIES = ("css", "js", "res")


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)

    for filename in PUBLIC_FILES:
        source = SOURCE / filename
        if not source.is_file():
            raise FileNotFoundError(f"Required Companion file is missing: {source}")
        shutil.copy2(source, DESTINATION / filename)

    logo = ROOT / "logo.png"
    if not logo.is_file():
        raise FileNotFoundError(f"Required application logo is missing: {logo}")
    shutil.copy2(logo, DESTINATION / "logo.png")

    for directory in PUBLIC_DIRECTORIES:
        source = SOURCE / directory
        if not source.is_dir():
            raise FileNotFoundError(f"Required Companion directory is missing: {source}")
        shutil.copytree(source, DESTINATION / directory, dirs_exist_ok=True)


if __name__ == "__main__":
    main()
