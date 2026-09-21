"""
S3 File Organizer
A command-line tool for managing files in an AWS S3 bucket.

Usage:
    python s3_organizer.py list-buckets
    python s3_organizer.py list-files <bucket-name>
    python s3_organizer.py upload <bucket-name> <local-file-path>
    python s3_organizer.py download <bucket-name> <s3-key> <local-destination>
    python s3_organizer.py organize <bucket-name> [--dry-run]
"""

import os
import sys
import logging
import argparse

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("s3_organizer")

EXTENSION_FOLDERS = {
    "jpg": "images", "jpeg": "images", "png": "images", "gif": "images",
    "pdf": "documents", "doc": "documents", "docx": "documents", "txt": "documents",
    "mp4": "videos", "mov": "videos", "avi": "videos",
    "mp3": "audio", "wav": "audio",
    "zip": "archives", "tar": "archives", "gz": "archives",
}


def get_s3_client():
    """Create and return an S3 client."""
    return boto3.client("s3")


def list_buckets(s3=None):
    """List all S3 buckets in the account."""
    s3 = s3 or get_s3_client()
    try:
        response = s3.list_buckets()
        buckets = response.get("Buckets", [])
        if not buckets:
            logger.info("No buckets found in this account.")
            return []
        logger.info("Found %d bucket(s):", len(buckets))
        for bucket in buckets:
            print(f"  - {bucket['Name']} (created {bucket['CreationDate']})")
        return buckets
    except NoCredentialsError:
        logger.error("AWS credentials not found. Run 'aws configure' first.")
    except ClientError as e:
        logger.error("Error listing buckets: %s", e)
    return []


def list_files(bucket_name, s3=None):
    """List all objects/files in a given bucket."""
    s3 = s3 or get_s3_client()
    try:
        response = s3.list_objects_v2(Bucket=bucket_name)
        objects = response.get("Contents", [])
        if not objects:
            logger.info("No files found in bucket '%s'.", bucket_name)
            return []
        logger.info("Found %d file(s) in '%s':", len(objects), bucket_name)
        for obj in objects:
            size_kb = obj["Size"] / 1024
            print(f"  - {obj['Key']} ({size_kb:.1f} KB)")
        return objects
    except ClientError as e:
        logger.error("Error listing files: %s", e)
        return []


def upload_file(bucket_name, local_path, s3=None):
    """Upload a local file to the given bucket."""
    if not os.path.isfile(local_path):
        logger.error("Local file '%s' does not exist.", local_path)
        return False
    s3 = s3 or get_s3_client()
    file_name = os.path.basename(local_path)
    try:
        s3.upload_file(local_path, bucket_name, file_name)
        logger.info("Uploaded '%s' to 's3://%s/%s'", local_path, bucket_name, file_name)
        return True
    except ClientError as e:
        logger.error("Error uploading file: %s", e)
        return False


def download_file(bucket_name, s3_key, destination, s3=None):
    """Download a file from the given bucket to a local destination."""
    s3 = s3 or get_s3_client()
    try:
        s3.download_file(bucket_name, s3_key, destination)
        logger.info("Downloaded 's3://%s/%s' to '%s'", bucket_name, s3_key, destination)
        return True
    except ClientError as e:
        logger.error("Error downloading file: %s", e)
        return False


def get_target_folder(key):
    """Work out which folder a given S3 key should be organized into."""
    extension = key.split(".")[-1].lower() if "." in key else ""
    return EXTENSION_FOLDERS.get(extension, "other")


def organize_bucket(bucket_name, s3=None, dry_run=False):
    """
    Organize files in a bucket into folders by file extension.
    e.g. photo.jpg -> images/photo.jpg, report.pdf -> documents/report.pdf

    If dry_run is True, prints what would happen without changing anything.
    """
    s3 = s3 or get_s3_client()
    try:
        response = s3.list_objects_v2(Bucket=bucket_name)
        objects = response.get("Contents", [])
        if not objects:
            logger.info("No files to organize in '%s'.", bucket_name)
            return 0

        moved_count = 0
        for obj in objects:
            key = obj["Key"]
            # Skip files that are already organized (already in a folder)
            if "/" in key:
                continue

            folder = get_target_folder(key)
            new_key = f"{folder}/{key}"

            if dry_run:
                print(f"  [DRY RUN] Would move '{key}' -> '{new_key}'")
                moved_count += 1
                continue

            s3.copy_object(
                Bucket=bucket_name,
                CopySource={"Bucket": bucket_name, "Key": key},
                Key=new_key,
            )
            s3.delete_object(Bucket=bucket_name, Key=key)
            print(f"  Moved '{key}' -> '{new_key}'")
            moved_count += 1

        verb = "Would organize" if dry_run else "Organized"
        logger.info("%s %d file(s) in '%s'.", verb, moved_count, bucket_name)
        return moved_count
    except ClientError as e:
        logger.error("Error organizing bucket: %s", e)
        return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="s3_organizer.py",
        description="A CLI tool for managing files in an AWS S3 bucket.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-buckets", help="List all S3 buckets in the account")

    p_list_files = subparsers.add_parser("list-files", help="List files in a bucket")
    p_list_files.add_argument("bucket", help="Name of the S3 bucket")

    p_upload = subparsers.add_parser("upload", help="Upload a local file to a bucket")
    p_upload.add_argument("bucket", help="Name of the S3 bucket")
    p_upload.add_argument("local_path", help="Path to the local file")

    p_download = subparsers.add_parser("download", help="Download a file from a bucket")
    p_download.add_argument("bucket", help="Name of the S3 bucket")
    p_download.add_argument("s3_key", help="Key (path) of the file in the bucket")
    p_download.add_argument("destination", help="Local destination path")

    p_organize = subparsers.add_parser("organize", help="Organize a bucket's files by type")
    p_organize.add_argument("bucket", help="Name of the S3 bucket")
    p_organize.add_argument(
        "--dry-run", action="store_true",
        help="Preview what would be moved without actually moving anything",
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "list-buckets":
        list_buckets()
    elif args.command == "list-files":
        list_files(args.bucket)
    elif args.command == "upload":
        upload_file(args.bucket, args.local_path)
    elif args.command == "download":
        download_file(args.bucket, args.s3_key, args.destination)
    elif args.command == "organize":
        organize_bucket(args.bucket, dry_run=args.dry_run)


if __name__ == "__main__":
    main()


def organize_bucket(bucket_name):
    """
    Organize files in a bucket into folders by file extension.
    e.g. photo.jpg -> images/photo.jpg, report.pdf -> documents/report.pdf
    """
    s3 = get_s3_client()
    extension_folders = {
        "jpg": "images", "jpeg": "images", "png": "images", "gif": "images",
        "pdf": "documents", "doc": "documents", "docx": "documents", "txt": "documents",
        "mp4": "videos", "mov": "videos", "avi": "videos",
        "mp3": "audio", "wav": "audio",
        "zip": "archives", "tar": "archives", "gz": "archives",
    }

    try:
        response = s3.list_objects_v2(Bucket=bucket_name)
        objects = response.get("Contents", [])
        if not objects:
            print(f"No files to organize in '{bucket_name}'.")
            return

        moved_count = 0
        for obj in objects:
            key = obj["Key"]
            # Skip files that are already organized (already in a folder)
            if "/" in key:
                continue

            extension = key.split(".")[-1].lower() if "." in key else ""
            folder = extension_folders.get(extension, "other")
            new_key = f"{folder}/{key}"

            s3.copy_object(
                Bucket=bucket_name,
                CopySource={"Bucket": bucket_name, "Key": key},
                Key=new_key,
            )
            s3.delete_object(Bucket=bucket_name, Key=key)
            print(f"  Moved '{key}' -> '{new_key}'")
            moved_count += 1

        print(f"Organized {moved_count} file(s) in '{bucket_name}'.")
    except ClientError as e:
        print(f"Error organizing bucket: {e}")


def print_usage():
    print(__doc__)


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1]

    if command == "list-buckets":
        list_buckets()
    elif command == "list-files" and len(sys.argv) == 3:
        list_files(sys.argv[2])
    elif command == "upload" and len(sys.argv) == 4:
        upload_file(sys.argv[2], sys.argv[3])
    elif command == "download" and len(sys.argv) == 5:
        download_file(sys.argv[2], sys.argv[3], sys.argv[4])
    elif command == "organize" and len(sys.argv) == 3:
        organize_bucket(sys.argv[2])
    else:
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
