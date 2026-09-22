"""
Unit tests for s3_organizer.py.
Run from the project root with:  python -m unittest discover tests -v
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import s3_organizer  # noqa: E402  (import after sys.path change)


def make_mock_s3(pages_of_keys):
    """
    Build a fake S3 client whose paginator returns the given pages.
    pages_of_keys is a list of pages, each page a list of object keys.
    An empty page mimics what S3 sends back for an empty bucket (no "Contents").
    """
    s3 = MagicMock()
    pages = [
        {"Contents": [{"Key": key, "Size": 2048} for key in keys]} if keys else {}
        for keys in pages_of_keys
    ]
    s3.get_paginator.return_value.paginate.return_value = pages
    return s3


class TestGetFolderForKey(unittest.TestCase):
    def test_known_extensions_map_to_their_folder(self):
        cases = {
            "photo.jpg": "images",
            "photo.jpeg": "images",
            "logo.png": "images",
            "report.pdf": "documents",
            "notes.txt": "documents",
            "clip.mp4": "videos",
            "song.mp3": "audio",
            "backup.zip": "archives",
        }
        for key, expected in cases.items():
            with self.subTest(key=key):
                self.assertEqual(s3_organizer.get_folder_for_key(key), expected)

    def test_extension_matching_ignores_case(self):
        self.assertEqual(s3_organizer.get_folder_for_key("PHOTO.JPG"), "images")
        self.assertEqual(s3_organizer.get_folder_for_key("Report.PdF"), "documents")

    def test_unknown_extension_goes_to_other(self):
        self.assertEqual(s3_organizer.get_folder_for_key("data.xyz"), "other")

    def test_no_extension_goes_to_other(self):
        self.assertEqual(s3_organizer.get_folder_for_key("README"), "other")

    def test_dotfile_goes_to_other(self):
        # ".gitignore" has no extension, its whole name starts with a dot
        self.assertEqual(s3_organizer.get_folder_for_key(".gitignore"), "other")

    def test_only_the_last_extension_counts(self):
        self.assertEqual(s3_organizer.get_folder_for_key("backup.tar.gz"), "archives")
        self.assertEqual(s3_organizer.get_folder_for_key("my.holiday.photo.png"), "images")


class TestIterObjects(unittest.TestCase):
    def test_yields_objects_from_every_page(self):
        s3 = make_mock_s3([["a.txt", "b.jpg"], ["c.pdf"]])
        keys = [obj["Key"] for obj in s3_organizer.iter_objects(s3, "my-bucket")]
        self.assertEqual(keys, ["a.txt", "b.jpg", "c.pdf"])

    def test_asks_for_the_right_bucket_with_a_paginator(self):
        s3 = make_mock_s3([["a.txt"]])
        list(s3_organizer.iter_objects(s3, "my-bucket"))
        s3.get_paginator.assert_called_once_with("list_objects_v2")
        s3.get_paginator.return_value.paginate.assert_called_once_with(Bucket="my-bucket")

    def test_empty_bucket_yields_nothing(self):
        s3 = make_mock_s3([[]])
        self.assertEqual(list(s3_organizer.iter_objects(s3, "my-bucket")), [])


class TestOrganizeBucket(unittest.TestCase):
    def run_organize(self, pages_of_keys):
        s3 = make_mock_s3(pages_of_keys)
        with patch.object(s3_organizer, "get_s3_client", return_value=s3):
            s3_organizer.organize_bucket("my-bucket")
        return s3

    def test_moves_loose_files_into_type_folders(self):
        s3 = self.run_organize([["photo.jpg", "report.pdf", "data.xyz"]])
        for old_key, new_key in [
            ("photo.jpg", "images/photo.jpg"),
            ("report.pdf", "documents/report.pdf"),
            ("data.xyz", "other/data.xyz"),
        ]:
            s3.copy_object.assert_any_call(
                Bucket="my-bucket",
                CopySource={"Bucket": "my-bucket", "Key": old_key},
                Key=new_key,
            )
            s3.delete_object.assert_any_call(Bucket="my-bucket", Key=old_key)

    def test_skips_files_already_inside_a_folder(self):
        s3 = self.run_organize([["images/old.png", "photo.jpg"]])
        self.assertEqual(s3.copy_object.call_count, 1)
        self.assertEqual(s3.delete_object.call_count, 1)

    def test_copies_before_deleting_each_file(self):
        # If the delete ran first and the copy then failed, the file would be lost
        s3 = self.run_organize([["a.jpg", "b.pdf"]])
        moves = [c[0] for c in s3.method_calls if c[0] in ("copy_object", "delete_object")]
        self.assertEqual(moves, ["copy_object", "delete_object"] * 2)

    def test_organizes_files_beyond_the_first_page(self):
        s3 = self.run_organize([["a.jpg"], ["b.pdf"]])
        self.assertEqual(s3.copy_object.call_count, 2)

    def test_empty_bucket_changes_nothing(self):
        s3 = self.run_organize([[]])
        s3.copy_object.assert_not_called()
        s3.delete_object.assert_not_called()

class TestOrganizeDryRun(unittest.TestCase):
    def test_dry_run_reports_moves_but_changes_nothing(self):
        s3 = make_mock_s3([["photo.jpg", "report.pdf"]])
        with patch.object(s3_organizer, "get_s3_client", return_value=s3):
            with self.assertLogs("s3_organizer", level="INFO") as logs:
                s3_organizer.organize_bucket("my-bucket", dry_run=True)
        s3.copy_object.assert_not_called()
        s3.delete_object.assert_not_called()
        output = "\n".join(logs.output)
        self.assertIn("Would move 'photo.jpg' -> 'images/photo.jpg'", output)
        self.assertIn("Would move 'report.pdf' -> 'documents/report.pdf'", output)


class TestBuildParser(unittest.TestCase):
    def test_organize_defaults_to_a_real_run(self):
        args = s3_organizer.build_parser().parse_args(["organize", "my-bucket"])
        self.assertEqual(args.command, "organize")
        self.assertEqual(args.bucket, "my-bucket")
        self.assertFalse(args.dry_run)

    def test_organize_accepts_dry_run_flag(self):
        args = s3_organizer.build_parser().parse_args(["organize", "my-bucket", "--dry-run"])
        self.assertTrue(args.dry_run)

    def test_download_takes_bucket_key_and_destination(self):
        args = s3_organizer.build_parser().parse_args(["download", "b", "photo.jpg", "./out.jpg"])
        self.assertEqual((args.bucket, args.key, args.destination), ("b", "photo.jpg", "./out.jpg"))

    def test_missing_command_is_rejected(self):
        with self.assertRaises(SystemExit):
            s3_organizer.build_parser().parse_args([])

    def test_missing_argument_is_rejected(self):
        with self.assertRaises(SystemExit):
            s3_organizer.build_parser().parse_args(["upload", "only-a-bucket"])

def make_client_error(code="AccessDenied", operation="ListObjectsV2"):
    return ClientError({"Error": {"Code": code, "Message": "test error"}}, operation)


class TestMainErrorHandling(unittest.TestCase):
    def test_success_returns_zero(self):
        with patch.object(s3_organizer, "list_buckets") as fake:
            self.assertEqual(s3_organizer.main(["list-buckets"]), 0)
        fake.assert_called_once()

    def test_missing_credentials_returns_one_with_helpful_message(self):
        with patch.object(s3_organizer, "list_buckets", side_effect=NoCredentialsError()):
            with self.assertLogs("s3_organizer", level="ERROR") as logs:
                code = s3_organizer.main(["list-buckets"])
        self.assertEqual(code, 1)
        self.assertIn("aws configure", logs.output[0])

    def test_aws_client_error_returns_one(self):
        with patch.object(s3_organizer, "list_files", side_effect=make_client_error("NoSuchBucket")):
            with self.assertLogs("s3_organizer", level="ERROR") as logs:
                code = s3_organizer.main(["list-files", "missing-bucket"])
        self.assertEqual(code, 1)
        self.assertIn("NoSuchBucket", logs.output[0])

    def test_failed_upload_returns_one(self):
        # boto3's upload_file raises S3UploadFailedError, not ClientError
        with patch.object(s3_organizer, "upload_file", side_effect=S3UploadFailedError("boom")):
            with self.assertLogs("s3_organizer", level="ERROR"):
                code = s3_organizer.main(["upload", "my-bucket", "file.txt"])
        self.assertEqual(code, 1)

    def test_connection_problem_returns_one(self):
        with patch.object(s3_organizer, "list_buckets", side_effect=BotoCoreError()):
            with self.assertLogs("s3_organizer", level="ERROR"):
                self.assertEqual(s3_organizer.main(["list-buckets"]), 1)

    def test_missing_local_file_fails_before_touching_aws(self):
        with patch.object(s3_organizer, "get_s3_client") as fake_client:
            with self.assertLogs("s3_organizer", level="ERROR") as logs:
                code = s3_organizer.main(["upload", "my-bucket", "/no/such/file.txt"])
        self.assertEqual(code, 1)
        self.assertIn("does not exist", logs.output[0])
        fake_client.assert_not_called()


class TestUploadAndList(unittest.TestCase):
    def test_upload_uses_the_file_name_as_the_key(self):
        s3 = MagicMock()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "photo.jpg")
            open(path, "w").close()
            with patch.object(s3_organizer, "get_s3_client", return_value=s3):
                with self.assertLogs("s3_organizer", level="INFO"):
                    s3_organizer.upload_file("my-bucket", path)
        s3.upload_file.assert_called_once_with(path, "my-bucket", "photo.jpg")

    def test_list_files_reports_size_in_kb(self):
        s3 = make_mock_s3([["photo.jpg"]])
        with patch.object(s3_organizer, "get_s3_client", return_value=s3):
            with self.assertLogs("s3_organizer", level="INFO") as logs:
                s3_organizer.list_files("my-bucket")
        self.assertIn("photo.jpg (2.0 KB)", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()