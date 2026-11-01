import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path


ANDROID_NAMESPACE = "http://schemas.android.com/apk/res/android"
ANDROID = f"{{{ANDROID_NAMESPACE}}}"


def set_manifest_attributes(manifest_path):
    ET.register_namespace("android", ANDROID_NAMESPACE)
    tree = ET.parse(manifest_path)
    root = tree.getroot()
    application = root.find("application")
    if application is None:
        raise RuntimeError(f"No application element in {manifest_path}")

    application.set(ANDROID + "usesCleartextTraffic", "true")
    permissions = {
        element.get(ANDROID + "name")
        for element in root.findall("uses-permission")
    }
    for permission in ("android.permission.INTERNET", "android.permission.CAMERA"):
        if permission not in permissions:
            ET.SubElement(
                root,
                "uses-permission",
                {ANDROID + "name": permission}
            )

    main_activity = next(
        (
            activity
            for activity in application.findall("activity")
            if activity.get(ANDROID + "name", "").endswith("MainActivity")
        ),
        None
    )
    if main_activity is None:
        raise RuntimeError(f"No MainActivity element in {manifest_path}")
    main_activity.set(ANDROID + "screenOrientation", "landscape")
    tree.write(manifest_path, encoding="utf-8", xml_declaration=True)


def set_gradle_version(build_file, version_code, version_name):
    contents = build_file.read_text(encoding="utf-8")
    contents, code_count = re.subn(
        r"(?m)^(\s*versionCode\s+)\d+\s*$",
        rf"\g<1>{version_code}",
        contents
    )
    contents, name_count = re.subn(
        r"""(?m)^(\s*versionName\s+)['"][^'"]*['"]\s*$""",
        lambda match: f'{match.group(1)}"{version_name}"',
        contents
    )
    if code_count != 1 or name_count != 1:
        raise RuntimeError(
            f"Expected one versionCode and versionName in {build_file}; "
            f"found {code_count} and {name_count}"
        )
    build_file.write_text(contents, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-code", type=int, required=True)
    parser.add_argument("--version-name", required=True)
    args = parser.parse_args()

    android_root = Path("android")
    manifest_path = android_root / "app" / "src" / "main" / "AndroidManifest.xml"
    build_file = android_root / "app" / "build.gradle"
    if not manifest_path.is_file() or not build_file.is_file():
        raise FileNotFoundError(
            "Android project is missing. Run 'npx cap add android' first."
        )

    set_manifest_attributes(manifest_path)
    set_gradle_version(build_file, args.version_code, args.version_name)


if __name__ == "__main__":
    main()
