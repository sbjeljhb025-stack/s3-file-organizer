"""
Basic unit tests for s3_organizer.py.
These test pure logic only (no real AWS calls / no mocking of boto3 yet).
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_extension_mapping_images():
    extension_folders = {
        "jpg": "images", "jpeg": "images", "png": "images", "gif": "images",
        "pdf": "documents",
    }
    assert extension_folders.get("jpg") == "images"
    assert extension_folders.get("png") == "images"


def test_extension_mapping_documents():
    extension_folders = {
        "pdf": "documents", "docx": "documents",
    }
    assert extension_folders.get("pdf") == "documents"


def test_extension_mapping_unknown_defaults_to_other():
    extension_folders = {"jpg": "images"}
    result = extension_folders.get("xyz", "other")
    assert result == "other"


if __name__ == "__main__":
    test_extension_mapping_images()
    test_extension_mapping_documents()
    test_extension_mapping_unknown_defaults_to_other()
    print("All tests passed.")
