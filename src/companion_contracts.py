import json
import os
import re
import tempfile
from pathlib import Path


MAX_CONTRACT_SIZE = 2 * 1024 * 1024
CONTRACT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def get_contract_directory(configured_path=None):
    if configured_path:
        return Path(configured_path).expanduser()

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "LeprendiX" / "contracts"
    return Path.home() / ".local" / "share" / "LeprendiX" / "contracts"


def validate_contract(contract, source="Vertrag"):
    if not isinstance(contract, dict):
        raise ValueError(f"{source}: Das JSON muss ein Objekt enthalten.")

    contract_id = contract.get("id")
    if (
        not isinstance(contract_id, str)
        or not CONTRACT_ID_PATTERN.fullmatch(contract_id)
        or contract_id == "contracts_index"
    ):
        raise ValueError(f"{source}: Ungültige Vertrags-ID.")

    if not isinstance(contract.get("title"), str) or not contract["title"].strip():
        raise ValueError(f"{source}: Der Vertragstitel fehlt.")
    if "required" in contract and not isinstance(contract["required"], bool):
        raise ValueError(f"{source}: Die Pflicht-Angabe muss Ja/Nein sein.")
    if "version" in contract and not isinstance(contract["version"], (str, int, float)):
        raise ValueError(f"{source}: Die Versionsangabe ist ungültig.")

    sections = contract.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError(f"{source}: Der Vertrag muss Abschnitte enthalten.")
    for section in sections:
        if (
            not isinstance(section, dict)
            or not isinstance(section.get("heading"), str)
            or not isinstance(section.get("text"), str)
        ):
            raise ValueError(f"{source}: Ein Vertragsabschnitt ist ungültig.")

    checkboxes = contract.get("checkboxes", [])
    if not isinstance(checkboxes, list):
        raise ValueError(f"{source}: Die Zustimmungspunkte sind ungültig.")
    seen_checkbox_ids = set()
    for checkbox in checkboxes:
        if (
            not isinstance(checkbox, dict)
            or not isinstance(checkbox.get("id"), str)
            or not checkbox["id"].strip()
            or not isinstance(checkbox.get("label"), str)
            or not isinstance(checkbox.get("required", False), bool)
        ):
            raise ValueError(f"{source}: Ein Zustimmungspunkt ist ungültig.")
        if checkbox["id"] in seen_checkbox_ids:
            raise ValueError(f"{source}: Zustimmungspunkt-IDs müssen eindeutig sein.")
        seen_checkbox_ids.add(checkbox["id"])

    return contract


def read_contract_files(file_paths):
    contracts = []
    seen_ids = set()
    for file_path in file_paths:
        path = Path(file_path)
        if path.stat().st_size > MAX_CONTRACT_SIZE:
            raise ValueError(f"{path.name}: Die Datei ist größer als 2 MB.")
        try:
            contract = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f"{path.name}: Ungültige JSON-Datei ({error}).") from error
        validate_contract(contract, path.name)
        if contract["id"] in seen_ids:
            raise ValueError(f"{path.name}: Die Vertrags-ID wurde mehrfach ausgewählt.")
        seen_ids.add(contract["id"])
        contracts.append(contract)
    if not contracts:
        raise ValueError("Bitte mindestens eine Vertrags-JSON-Datei auswählen.")
    return contracts


def load_contracts(contract_directory):
    directory = Path(contract_directory)
    if not directory.is_dir():
        return []

    contracts = []
    for path in sorted(directory.glob("*.json")):
        if path.name == "contracts_index.json":
            continue
        if path.stat().st_size > MAX_CONTRACT_SIZE:
            raise ValueError(f"{path.name}: Die Datei ist größer als 2 MB.")
        try:
            contract = json.loads(path.read_text(encoding="utf-8"))
            validate_contract(contract, path.name)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            raise ValueError(f"{path.name}: Vertragsdatei ist ungültig ({error}).") from error
        if path.stem == contract["id"]:
            contracts.append(contract)
        else:
            raise ValueError(f"{path.name}: Dateiname und Vertrags-ID stimmen nicht überein.")
    return contracts


def save_contract_files(file_paths, contract_directory):
    contracts = read_contract_files(file_paths)
    directory = Path(contract_directory)
    directory.mkdir(parents=True, exist_ok=True)

    merged = {contract["id"]: contract for contract in load_contracts(directory)}
    merged.update({contract["id"]: contract for contract in contracts})
    for contract in contracts:
        _atomic_write_json(directory / f"{contract['id']}.json", contract)

    index = {
        "contracts": [
            {
                "id": contract["id"],
                "file": f"{contract['id']}.json",
                "title": contract["title"],
                "badge": "Pflicht" if contract.get("required") else "Optional",
                "required": bool(contract.get("required", False)),
                "enabled": True,
                "version": str(contract.get("version") or "1.0"),
            }
            for contract in sorted(merged.values(), key=lambda item: item["title"].casefold())
        ]
    }
    _atomic_write_json(directory / "contracts_index.json", index)
    return contracts


def _atomic_write_json(path, data):
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    except Exception:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass
        raise
