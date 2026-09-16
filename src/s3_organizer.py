"""
S3 File Organizer
A simple CLI tool for managing files in an AWS S3 bucket.

Usage:
    python s3_organizer.py list-buckets
    python s3_organizer.py list-files <bucket-name>
    python s3_organizer.py upload <bucket-name> <local-file-path>
    python s3_organizer.py download <bucket-name> <s3-key> <local-destination>
    python s3_organizer.py organize <bucket-name>
"""

import sys
import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


def get_s3_client():
    """Create and return an S3 client."""
    return boto3.client("s3")


def list_buckets():
    """List all S3 buckets in the account."""
    s3 = get_s3_client()
    try:
        response = s3.list_buckets()
        buckets = response.get("Buckets", [])
        if not buckets:
            print("No buckets found in this account.")
            return
        print(f"Found {len(buckets)} bucket(s):")
        for bucket in buckets:
            print(f"  - {bucket['Name']} (created {bucket['CreationDate']})")
    except NoCredentialsError:
        print("Error: AWS credentials not found. Run 'aws configure' first.")
    except ClientError as e:
        print(f"Error listing buckets: {e}")


def list_files(bucket_name):
    """List all objects/files in a given bucket."""
    s3 = get_s3_client()
    try:
        response = s3.list_objects_v2(Bucket=bucket_name)
        objects = response.get("Contents", [])
        if not objects:
            print(f"No files found in bucket '{bucket_name}'.")
            return
        print(f"Found {len(objects)} file(s) in '{bucket_name}':")
        for obj in objects:
            size_kb = obj["Size"] / 1024
            print(f"  - {obj['Key']} ({size_kb:.1f} KB)")
    except ClientError as e:
        print(f"Error listing files: {e}")


def upload_file(bucket_name, local_path):
    """Upload a local file to the given bucket."""
    if not os.path.isfile(local_path):
        print(f"Error: local file '{local_path}' does not exist.")
        return
    s3 = get_s3_client()
    file_name = os.path.basename(local_path)
    try:
        s3.upload_file(local_path, bucket_name, file_name)
        print(f"Uploaded '{local_path}' to 's3://{bucket_name}/{file_name}'")
    except ClientError as e:
        print(f"Error uploading file: {e}")


def download_file(bucket_name, s3_key, destination):
    """Download a file from the given bucket to a local destination."""
    s3 = get_s3_client()
    try:
        s3.download_file(bucket_name, s3_key, destination)
        print(f"Downloaded 's3://{bucket_name}/{s3_key}' to '{destination}'")
    except ClientError as e:
        print(f"Error downloading file: {e}")


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
