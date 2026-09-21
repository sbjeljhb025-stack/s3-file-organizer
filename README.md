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
- **Dry run** — preview exactly what `organize` would move, without changing
  anything (`--dry-run`)
- Works on buckets of any size (results are paginated, not capped at 1000 files)
- Clear error messages and a non-zero exit code when something goes wrong

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

# Preview what organize would do (nothing is changed)
python src/s3_organizer.py organize my-bucket-name --dry-run

# Organize a bucket's files into folders by type
python src/s3_organizer.py organize my-bucket-name

# See all commands
python src/s3_organizer.py --help
```

> **Careful:** `organize` *moves* files (copy, then delete the original).
> Try `--dry-run` first, and use a test bucket while experimenting.

## Running tests

```bash
python -m unittest discover tests -v
```

The tests use `unittest.mock` to stand in for the S3 client, so they run
without an AWS account or internet connection. They cover the sorting logic,
pagination, the organize/dry-run behaviour, argument parsing and error handling.

## Design decisions

- **Sorting logic is a pure function** (`get_folder_for_key`) so it can be tested
  without touching AWS.
- **Copy first, delete second** when moving a file: if the copy fails, the
  original is still there.
- **Full listing before moving anything**, so the bucket is never modified while
  it is being paged through.
- **One place handles errors** (`main`), so every command reports failures the
  same way and the process exits with code 1.
- **Mocked tests** keep the test suite fast, free, and safe: no real files are
  ever moved by a test.

## Known limitations

- `organize` only sorts files at the top level of the bucket; anything already
  inside a folder is left alone.
- If a file with the same name already exists in the target folder, it is
  overwritten.
- Only the extensions listed in `EXTENSION_FOLDERS` are recognised; everything
  else goes to `other/`.
- The tests use a mocked S3 client, so they do not prove the tool works against
  a real bucket — that is checked manually in the demo.

## Project structure

```
s3-file-organizer/
├── .github/workflows/
│   └── tests.yml         # runs the unit tests on every push
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

- Skip (or rename) files when the destination already exists, instead of overwriting
- A `--prefix` option to organize only part of a bucket
- Integration tests against a real throwaway bucket (or `moto`)
## WTC-KS95WMNR
## Author

Sbongakonke Jele — WeThinkCode student, Cloud Computing elective (2nd choice)