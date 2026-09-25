"""
S3 File Organizer
A simple CLI tool for managing files in an AWS S3 bucket.

Usage:
    python s3_organizer.py list-buckets
    python s3_organizer.py list-files <bucket-name>
    python s3_organizer.py upload <bucket-name> <local-file-path>
    python s3_organizer.py download <bucket-name> <s3-key> <local-destination>
    python s3_organizer.py organize <bucket-name> [--dry-run]
    python s3_organizer.py --help
"""

import argparse
import logging
import os
import sys

import boto3
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

logger = logging.getLogger("s3_organizer")


def get_s3_client():
    """Create and return an S3 client."""
    return boto3.client("s3")


# Which folder each file extension belongs in. Anything not listed goes to "other".
EXTENSION_FOLDERS = {
    "jpg": "images", "jpeg": "images", "png": "images", "gif": "images",
    "pdf": "documents", "doc": "documents", "docx": "documents", "txt": "documents",
    "mp4": "videos", "mov": "videos", "avi": "videos",
    "mp3": "audio", "wav": "audio",
    "zip": "archives", "tar": "archives", "gz": "archives",
}


def get_folder_for_key(key):
    """
    Return the folder a file should be sorted into, based on its extension.
    Pure logic (no AWS calls), so it is easy to unit test.

    "photo.JPG" -> "images", "notes.xyz" -> "other", "README" -> "other"
    """
    _, extension = os.path.splitext(key)
    return EXTENSION_FOLDERS.get(extension.lstrip(".").lower(), "other")


def iter_objects(s3, bucket_name):
    """
    Yield every object in a bucket, one dict at a time.

    S3 returns at most 1000 objects per request, so a single list_objects_v2
    call silently misses everything after the first 1000. The paginator keeps
    asking for the next page until the bucket is exhausted.
    """
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket_name):
        # An empty bucket returns a page with no "Contents" key at all
        yield from page.get("Contents", [])


def list_buckets():
    """List all S3 buckets in the account."""
    s3 = get_s3_client()
    buckets = s3.list_buckets().get("Buckets", [])
    if not buckets:
        logger.info("No buckets found in this account.")
        return
    logger.info("Found %d bucket(s):", len(buckets))
    for bucket in buckets:
        logger.info("  - %s (created %s)", bucket["Name"], bucket["CreationDate"])


def list_files(bucket_name):
    """List all objects/files in a given bucket."""
    s3 = get_s3_client()
    objects = list(iter_objects(s3, bucket_name))
    if not objects:
        logger.info("No files found in bucket '%s'.", bucket_name)
        return
    logger.info("Found %d file(s) in '%s':", len(objects), bucket_name)
    for obj in objects:
        size_kb = obj["Size"] / 1024
        logger.info("  - %s (%.1f KB)", obj["Key"], size_kb)


def upload_file(bucket_name, local_path):
    """Upload a local file to the given bucket."""
    if not os.path.isfile(local_path):
        raise FileNotFoundError(f"local file '{local_path}' does not exist")
    s3 = get_s3_client()
    file_name = os.path.basename(local_path)
    s3.upload_file(local_path, bucket_name, file_name)
    logger.info("Uploaded '%s' to 's3://%s/%s'", local_path, bucket_name, file_name)


def download_file(bucket_name, s3_key, destination):
    """Download a file from the given bucket to a local destination."""
    s3 = get_s3_client()
    s3.download_file(bucket_name, s3_key, destination)
    logger.info("Downloaded 's3://%s/%s' to '%s'", bucket_name, s3_key, destination)


def organize_bucket(bucket_name, dry_run=False):
    """
    Organize files in a bucket into folders by file extension.
    e.g. photo.jpg -> images/photo.jpg, report.pdf -> documents/report.pdf

    With dry_run=True, only report what would move; nothing in the bucket changes.
    """
    s3 = get_s3_client()
    # Collect the full listing first, so we never change the bucket while
    # we are still paging through it
    objects = list(iter_objects(s3, bucket_name))
    if not objects:
        logger.info("No files to organize in '%s'.", bucket_name)
        return

    moved_count = 0
    for obj in objects:
        key = obj["Key"]
        # Skip files that are already organized (already in a folder)
        if "/" in key:
            continue

        new_key = f"{get_folder_for_key(key)}/{key}"

        if dry_run:
            logger.info("  Would move '%s' -> '%s'", key, new_key)
        else:
            # Copy .......first, delete second: if the copy fails, the original is untouched
            s3.copy_object(
                Bucket=bucket_name,
                CopySource={"Bucket": bucket_name, "Key": key},
                Key=new_key,
            )
            s3.delete_object(Bucket=bucket_name, Key=key)
            logger.info("  Moved '%s' -> '%s'", key, new_key)
        moved_count += 1

    if dry_run:
        logger.info("Dry run: %d file(s) would be moved in '%s'. Nothing was changed.",
                    moved_count, bucket_name)
    else:
        logger.info("Organized %d file(s) in '%s'.", moved_count, bucket_name)


def build_parser():
    """Describe the command line: which commands exist and what arguments they take."""
    parser = argparse.ArgumentParser(
        description="Manage and organize files in an AWS S3 bucket."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("list-buckets", help="list all buckets in the account")

    list_files_cmd = commands.add_parser("list-files", help="list all files in a bucket")
    list_files_cmd.add_argument("bucket", help="bucket name")

    upload_cmd = commands.add_parser("upload", help="upload a local file to a bucket")
    upload_cmd.add_argument("bucket", help="bucket name")
    upload_cmd.add_argument("local_path", help="path of the local file to upload")

    download_cmd = commands.add_parser("download", help="download a file from a bucket")
    download_cmd.add_argument("bucket", help="bucket name")
    download_cmd.add_argument("key", help="name (key) of the file in the bucket")
    download_cmd.add_argument("destination", help="where to save the file locally")

    organize_cmd = commands.add_parser(
        "organize", help="sort loose files in a bucket into folders by type"
    )
    organize_cmd.add_argument("bucket", help="bucket name")
    organize_cmd.add_argument(
        "--dry-run", action="store_true",
        help="show what would be moved without changing anything",
    )
    return parser


def run_command(args):
    """Call the function that matches the command the user typed."""
    if args.command == "list-buckets":
        list_buckets()
    elif args.command == "list-files":
        list_files(args.bucket)
    elif args.command == "upload":
        upload_file(args.bucket, args.local_path)
    elif args.command == "download":
        download_file(args.bucket, args.key, args.destination)
    elif args.command == "organize":
        organize_bucket(args.bucket, dry_run=args.dry_run)


def main(argv=None):
    """Run the CLI. Returns 0 on success and 1 on failure (used as the exit code)."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = build_parser().parse_args(argv)

    try:
        run_command(args)
    except NoCredentialsError:
        logger.error("AWS credentials not found. Run 'aws configure' first.")
    except (ClientError, S3UploadFailedError) as e:
        logger.error("AWS error: %s", e)
    except BotoCoreError as e:
        # e.g. no internet connection or an invalid region
        logger.error("Could not talk to AWS: %s", e)
    except OSError as e:
        # Local file problems: missing upload file, bad download destination, ...
        logger.error("File error: %s", e)
    else:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())