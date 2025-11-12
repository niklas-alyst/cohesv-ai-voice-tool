"""S3 helper utilities for E2E tests."""

import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class S3File:
    """Represents an S3 file."""
    key: str
    size: int
    etag: str
    last_modified: str


async def wait_for_s3_files(
    s3_client,
    bucket: str,
    prefix: str,
    expected_file_patterns: List[str],
    timeout_seconds: int = 90,
    poll_interval: float = 2.0
) -> List[S3File]:
    """
    Poll S3 until expected files appear or timeout.

    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket name
        prefix: S3 key prefix (e.g., "company-id/job-to-be-done/")
        expected_file_patterns: List of substring patterns to match (e.g., ["_audio.ogg", "_full_text.txt"])
        timeout_seconds: Maximum time to wait
        poll_interval: Seconds between polls

    Returns:
        List of S3File objects that were found

    Raises:
        TimeoutError: If files don't appear within timeout
    """
    start_time = asyncio.get_event_loop().time()

    while True:
        elapsed = asyncio.get_event_loop().time() - start_time

        if elapsed > timeout_seconds:
            raise TimeoutError(
                f"Timeout waiting for S3 files with patterns {expected_file_patterns} "
                f"at prefix '{prefix}' after {timeout_seconds}s"
            )

        # List objects with prefix
        try:
            response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)

            if 'Contents' in response:
                files = [
                    S3File(
                        key=obj['Key'],
                        size=obj['Size'],
                        etag=obj['ETag'],
                        last_modified=obj['LastModified'].isoformat()
                    )
                    for obj in response['Contents']
                ]

                # Check if all expected patterns are found
                found_patterns = []
                for pattern in expected_file_patterns:
                    if any(pattern in f.key for f in files):
                        found_patterns.append(pattern)

                if len(found_patterns) == len(expected_file_patterns):
                    return files

        except Exception as e:
            # Log but continue polling
            print(f"Error listing S3 objects: {e}")

        # Wait before next poll
        await asyncio.sleep(poll_interval)


async def download_s3_file(
    s3_client,
    bucket: str,
    key: str
) -> bytes:
    """
    Download a file from S3.

    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        File contents as bytes
    """
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return response['Body'].read()


async def cleanup_s3_files(
    s3_client,
    bucket: str,
    prefix: str,
    dry_run: bool = False
) -> int:
    """
    Delete all S3 objects with a given prefix.

    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket name
        prefix: S3 key prefix
        dry_run: If True, only list files without deleting

    Returns:
        Number of files deleted (or would be deleted if dry_run=True)
    """
    deleted_count = 0

    # List all objects with prefix
    paginator = s3_client.get_paginator('list_objects_v2')

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        if 'Contents' not in page:
            continue

        objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]

        if not objects_to_delete:
            continue

        if dry_run:
            print(f"Would delete {len(objects_to_delete)} objects:")
            for obj in objects_to_delete:
                print(f"  - {obj['Key']}")
            deleted_count += len(objects_to_delete)
        else:
            response = s3_client.delete_objects(
                Bucket=bucket,
                Delete={'Objects': objects_to_delete}
            )
            deleted = len(response.get('Deleted', []))
            deleted_count += deleted

            if 'Errors' in response:
                print(f"Errors deleting some objects: {response['Errors']}")

    return deleted_count


def list_s3_files(
    s3_client,
    bucket: str,
    prefix: str,
    max_keys: int = 1000
) -> List[S3File]:
    """
    List S3 files with a given prefix.

    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket name
        prefix: S3 key prefix
        max_keys: Maximum number of keys to return

    Returns:
        List of S3File objects
    """
    response = s3_client.list_objects_v2(
        Bucket=bucket,
        Prefix=prefix,
        MaxKeys=max_keys
    )

    if 'Contents' not in response:
        return []

    return [
        S3File(
            key=obj['Key'],
            size=obj['Size'],
            etag=obj['ETag'],
            last_modified=obj['LastModified'].isoformat()
        )
        for obj in response['Contents']
    ]
