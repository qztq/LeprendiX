import os
import sys


def get_app_directory():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_resource_path(relative_path):
    bundle_directory = getattr(sys, "_MEIPASS", None)
    if bundle_directory:
        return os.path.join(bundle_directory, relative_path)
    return os.path.join(get_app_directory(), relative_path)
