"""
Demo script for the WeThinkCode video.
Simulates an S3 bucket using unittest.mock -- the same technique the test
suite uses -- so the tool can be demonstrated without a real AWS account.

Run from the project root with:
    python demo.py
"""

import datetime
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, "src")
import s3_organizer  # noqa: E402


def make_fake_bucket():
    """Build a fake S3 client pre-loaded with a bucket and some files."""
    s3 = MagicMock()

    s3.list_buckets.return_value = {
        "Buckets": [
            {"Name": "sbongakonke-demo-bucket", "CreationDate": datetime.datetime(2026, 9, 18)},
        ]
    }

    files = [
        ("holiday.jpg", 2_400_000),
        ("cv.pdf", 184_320),
        ("song.mp3", 5_100_000),
        ("notes", 812),          # no extension -> "other"
        ("images/old.png", 90_000),  # already organized -> skipped
    ]
    s3.get_paginator.return_value.paginate.return_value = [
        {"Contents": [{"Key": key, "Size": size} for key, size in files]}
    ]
    return s3


def run(argv):
    print(f"\n$ python src\\s3_organizer.py {' '.join(argv)}")
    s3_organizer.main(argv)


def main():
    fake_s3 = make_fake_bucket()
    with patch.object(s3_organizer, "get_s3_client", return_value=fake_s3):
        run(["list-buckets"])
        run(["list-files", "sbongakonke-demo-bucket"])
        run(["organize", "sbongakonke-demo-bucket", "--dry-run"])
        run(["organize", "sbongakonke-demo-bucket"])

    # A real error case, using the real AWS exception classes
    with patch.object(s3_organizer, "list_files", side_effect=s3_organizer.ClientError(
        {"Error": {"Code": "NoSuchBucket", "Message": "The specified bucket does not exist"}},
        "ListObjectsV2",
    )):
        run(["list-files", "a-bucket-that-does-not-exist"])


if __name__ == "__main__":
    main()