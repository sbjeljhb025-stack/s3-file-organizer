"""
Unit tests for s3_organizer.py.

Uses moto to mock S3 so these tests run without any real AWS account,
credentials, or network access.

Run with:
    pytest tests/test_s3_organizer.py
"""

import os
import sys

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from s3_organizer import (
    get_target_folder,
    list_buckets,
    list_files,
    upload_file,
    organize_bucket,
)

TEST_BUCKET = "test-bucket"
TEST_REGION = "us-east-1"


@pytest.fixture
def s3_client():
    """Provide a moto-mocked S3 client with one empty test bucket."""
    with mock_aws():
        client = boto3.client("s3", region_name=TEST_REGION)
        client.create_bucket(Bucket=TEST_BUCKET)
        yield client


# --- Pure logic tests (no AWS calls) ---

def test_get_target_folder_image():
    assert get_target_folder("photo.jpg") == "images"
    assert get_target_folder("photo.PNG") == "images"


def test_get_target_folder_document():
    assert get_target_folder("report.pdf") == "documents"
    assert get_target_folder("notes.docx") == "documents"


def test_get_target_folder_unknown_extension():
    assert get_target_folder("data.xyz") == "other"


def test_get_target_folder_no_extension():
    assert get_target_folder("README") == "other"


# --- Mocked-AWS tests ---

def test_list_buckets_returns_created_bucket(s3_client):
    buckets = list_buckets(s3=s3_client)
    names = [b["Name"] for b in buckets]
    assert TEST_BUCKET in names


def test_list_files_empty_bucket(s3_client):
    objects = list_files(TEST_BUCKET, s3=s3_client)
    assert objects == []


def test_upload_file_success(tmp_path, s3_client):
    local_file = tmp_path / "hello.txt"
    local_file.write_text("hello world")

    result = upload_file(TEST_BUCKET, str(local_file), s3=s3_client)
    assert result is True

    objects = list_files(TEST_BUCKET, s3=s3_client)
    keys = [obj["Key"] for obj in objects]
    assert "hello.txt" in keys


def test_upload_file_missing_local_file(s3_client):
    result = upload_file(TEST_BUCKET, "/nonexistent/path/file.txt", s3=s3_client)
    assert result is False


def test_organize_bucket_dry_run_does_not_move_files(tmp_path, s3_client):
    local_file = tmp_path / "photo.jpg"
    local_file.write_text("fake image bytes")
    upload_file(TEST_BUCKET, str(local_file), s3=s3_client)

    moved = organize_bucket(TEST_BUCKET, s3=s3_client, dry_run=True)
    assert moved == 1

    # File should still be at the top level, untouched
    objects = list_files(TEST_BUCKET, s3=s3_client)
    keys = [obj["Key"] for obj in objects]
    assert "photo.jpg" in keys
    assert "images/photo.jpg" not in keys


def test_organize_bucket_moves_file_into_folder(tmp_path, s3_client):
    local_file = tmp_path / "photo.jpg"
    local_file.write_text("fake image bytes")
    upload_file(TEST_BUCKET, str(local_file), s3=s3_client)

    moved = organize_bucket(TEST_BUCKET, s3=s3_client, dry_run=False)
    assert moved == 1

    objects = list_files(TEST_BUCKET, s3=s3_client)
    keys = [obj["Key"] for obj in objects]
    assert "images/photo.jpg" in keys
    assert "photo.jpg" not in keys


def test_organize_bucket_skips_already_organized_files(tmp_path, s3_client):
    # Upload directly to a subfolder to simulate an already-organized file
    s3_client.put_object(Bucket=TEST_BUCKET, Key="images/already-there.jpg", Body=b"x")

    moved = organize_bucket(TEST_BUCKET, s3=s3_client, dry_run=False)
    assert moved == 0