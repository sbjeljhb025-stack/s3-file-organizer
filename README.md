# S3 File Organizer

A simple Python command-line tool for managing files in an AWS S3 bucket:
list buckets, list files, upload, download, and automatically organize files
into folders by file type (images, documents, videos, audio, archives).

Built as my solo project for WeThinkCode's Cloud Computing elective.

## Features

- **List buckets** — see all S3 buckets in your AWS account
- **List files** — see all objects in a specific bucket
- **Upload** — push a local file to a bucket
- **Download** — pull a file from a bucket to your machine
- **Organize** — automatically sort loose files in a bucket into
  `images/`, `documents/`, `videos/`, `audio/`, `archives/`, or `other/`
  folders based on file extension

## Why this project

The Cloud Computing elective's entry filter is centered on AWS fundamentals
(the Management Console, core services, S3 storage). This project applies
those concepts directly by using `boto3` (the AWS SDK for Python) to interact
with S3 programmatically, rather than just clicking through the console.

## Requirements

- Python 3.8+
- An AWS account with an S3 bucket
- AWS credentials configured locally (`aws configure`)

## Setup

```bash
# Clone the repo
git clone <your-repo-url>
cd s3-file-organizer

# Install dependencies
pip install -r requirements.txt

# Configure AWS credentials (if not already done)
aws configure
```

## Usage

```bash
# List all buckets in your account
python src/s3_organizer.py list-buckets

# List all files in a specific bucket
python src/s3_organizer.py list-files my-bucket-name

# Upload a local file
python src/s3_organizer.py upload my-bucket-name ./photo.jpg

# Download a file
python src/s3_organizer.py download my-bucket-name photo.jpg ./downloaded-photo.jpg

# Organize a bucket's files into folders by type
python src/s3_organizer.py organize my-bucket-name
```

## Running tests

```bash
python tests/test_s3_organizer.py
```

## Project structure

```
s3-file-organizer/
├── src/
│   └── s3_organizer.py   # main CLI tool
├── tests/
│   └── test_s3_organizer.py
├── requirements.txt
├── .gitignore
└── README.md
```

## Demo video

[Link to unlisted YouTube demo — TODO: add once recorded]

## What I'd add next

- Mocked unit tests for the AWS-calling functions (using `moto` or `unittest.mock`)
- A `--dry-run` flag for `organize` so you can preview moves before they happen
- Basic logging instead of print statements
- Error handling for missing/expired AWS credentials with clearer messages

## Author

Sbongakonke Jele — WeThinkCode student, Cloud Computing elective (2nd choice)
