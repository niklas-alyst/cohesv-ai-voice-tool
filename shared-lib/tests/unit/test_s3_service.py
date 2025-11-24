import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from botocore.exceptions import ClientError
from datetime import datetime, timezone

from ai_voice_shared.services.s3_service import S3Service
from ai_voice_shared.settings import S3Settings
from ai_voice_shared.models import S3ListResponse

@pytest.fixture
def mock_boto3_session():
    """Fixture to mock boto3.Session and its client method."""
    with patch("boto3.Session") as mock_session:
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client
        yield mock_session, mock_client # Yield both the session mock and the client mock

@pytest.fixture
def mock_s3_settings(monkeypatch):
    """Fixture to provide mock S3Settings."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    return S3Settings(aws_region="us-east-1", s3_bucket_name="test-bucket")

@pytest.mark.asyncio
async def test_s3_service_init_with_settings(mock_boto3_session, mock_s3_settings):
    mock_session, mock_client = mock_boto3_session
    service = S3Service(settings=mock_s3_settings)
    assert service.bucket_name == "test-bucket"
    mock_session.assert_called_once_with(region_name="us-east-1")
    mock_session.return_value.client.assert_called_once_with("s3", config=ANY)

@pytest.mark.asyncio
async def test_s3_service_init_without_settings(mock_boto3_session, monkeypatch):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    mock_session, mock_client = mock_boto3_session
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("S3_BUCKET_NAME", "default-bucket")
    service = S3Service()
    assert service.bucket_name == "default-bucket"
    mock_session.assert_called_once_with(region_name="us-west-2")
    mock_session.return_value.client.assert_called_once_with("s3", config=ANY)

@pytest.mark.asyncio
async def test_exists_object_found(mock_boto3_session, mock_s3_settings):
    _, mock_client = mock_boto3_session
    service = S3Service(settings=mock_s3_settings)
    mock_client.head_object.return_value = {}
    result = await service.exists("test-key")
    assert result is True
    mock_client.head_object.assert_called_once_with(Bucket="test-bucket", Key="test-key")

@pytest.mark.asyncio
async def test_exists_object_not_found(mock_boto3_session, mock_s3_settings):
    _, mock_client = mock_boto3_session
    service = S3Service(settings=mock_s3_settings)
    mock_client.head_object.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadObject")
    result = await service.exists("non-existent-key")
    assert result is False

@pytest.mark.asyncio
async def test_exists_other_client_error(mock_boto3_session, mock_s3_settings):
    _, mock_client = mock_boto3_session
    service = S3Service(settings=mock_s3_settings)
    mock_client.head_object.side_effect = ClientError({"Error": {"Code": "500"}}, "HeadObject")
    with pytest.raises(ClientError):
        await service.exists("error-key")

@pytest.mark.asyncio
async def test_upload_new_file(mock_boto3_session, mock_s3_settings):
    _, mock_client = mock_boto3_session
    service = S3Service(settings=mock_s3_settings)
    service.exists = AsyncMock(return_value=False) # Mock exists to return False
    
    key = "new-file.txt"
    data = b"hello world"
    content_type = "text/plain"
    
    uploaded_key = await service.upload(data, key, content_type)
    
    assert uploaded_key == key
    service.exists.assert_called_once_with(key)
    mock_client.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key=key,
        Body=data,
        ContentType=content_type,
    )

@pytest.mark.asyncio
async def test_upload_file_exists_no_overwrite(mock_boto3_session, mock_s3_settings):
    _, mock_client = mock_boto3_session
    service = S3Service(settings=mock_s3_settings)
    service.exists = AsyncMock(return_value=True) # Mock exists to return True
    
    key = "existing-file.txt"
    data = b"hello world"
    content_type = "text/plain"
    
    with pytest.raises(FileExistsError):
        await service.upload(data, key, content_type, overwrite=False)
    
    service.exists.assert_called_once_with(key)
    mock_client.put_object.assert_not_called()

@pytest.mark.asyncio
async def test_upload_file_exists_with_overwrite(mock_boto3_session, mock_s3_settings):
    _, mock_client = mock_boto3_session
    service = S3Service(settings=mock_s3_settings)
    service.exists = AsyncMock(return_value=True) # Mock exists to return True
    
    key = "existing-file.txt"
    data = b"hello world"
    content_type = "text/plain"
    
    uploaded_key = await service.upload(data, key, content_type, overwrite=True)
    
    assert uploaded_key == key
    service.exists.assert_called_once_with(key)
    mock_client.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key=key,
        Body=data,
        ContentType=content_type,
    )

@pytest.mark.asyncio
async def test_download_success(mock_boto3_session, mock_s3_settings):
    _, mock_client = mock_boto3_session
    service = S3Service(settings=mock_s3_settings)
    mock_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"downloaded data")}
    
    data = await service.download("download-key")
    
    assert data == b"downloaded data"
    mock_client.get_object.assert_called_once_with(Bucket="test-bucket", Key="download-key")

@pytest.mark.asyncio
async def test_delete_success(mock_boto3_session, mock_s3_settings):
    _, mock_client = mock_boto3_session
    service = S3Service(settings=mock_s3_settings)
    mock_client.delete_object.return_value = {}
    
    await service.delete("delete-key")
    
    mock_client.delete_object.assert_called_once_with(Bucket="test-bucket", Key="delete-key")

@pytest.mark.asyncio
async def test_list_objects_no_continuation_token(mock_boto3_session, mock_s3_settings):
    _, mock_client = mock_boto3_session
    service = S3Service(settings=mock_s3_settings)
    
    mock_client.list_objects_v2.return_value = {
        "Contents": [
            {
                "Key": "company1/intent1/file1.txt",
                "ETag": '"etag1"',
                "Size": 100,
                "LastModified": datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            },
            {
                "Key": "company1/intent1/file2.txt",
                "ETag": '"etag2"',
                "Size": 200,
                "LastModified": datetime(2023, 1, 2, 13, 0, 0, tzinfo=timezone.utc),
            },
        ],
        "IsTruncated": False,
    }
    
    response = await service.list_objects("company1", "intent1")
    
    assert isinstance(response, S3ListResponse)
    assert len(response.files) == 2
    assert response.files[0].key == "company1/intent1/file1.txt"
    assert response.files[0].last_modified == "2023-01-01T12:00:00+00:00"
    assert response.nextContinuationToken is None
    mock_client.list_objects_v2.assert_called_once_with(
        Bucket="test-bucket", Prefix="company1/intent1/", MaxKeys=1000
    )

@pytest.mark.asyncio
async def test_list_objects_with_continuation_token(mock_boto3_session, mock_s3_settings):
    _, mock_client = mock_boto3_session
    service = S3Service(settings=mock_s3_settings)
    
    mock_client.list_objects_v2.return_value = {
        "Contents": [
            {
                "Key": "company1/intent1/file3.txt",
                "ETag": '"etag3"',
                "Size": 300,
                "LastModified": datetime(2023, 1, 3, 14, 0, 0, tzinfo=timezone.utc),
            },
        ],
        "IsTruncated": True,
        "NextContinuationToken": "next-token-123",
    }
    
    response = await service.list_objects("company1", "intent1", continuation_token="prev-token-abc")
    
    assert len(response.files) == 1
    assert response.files[0].key == "company1/intent1/file3.txt"
    assert response.nextContinuationToken == "next-token-123"
    mock_client.list_objects_v2.assert_called_once_with(
        Bucket="test-bucket", Prefix="company1/intent1/", MaxKeys=1000, ContinuationToken="prev-token-abc"
    )

@pytest.mark.asyncio
async def test_list_objects_no_contents(mock_boto3_session, mock_s3_settings):
    _, mock_client = mock_boto3_session
    service = S3Service(settings=mock_s3_settings)
    mock_client.list_objects_v2.return_value = {"IsTruncated": False}
    
    response = await service.list_objects("company1", "intent1")
    
    assert len(response.files) == 0
    assert response.nextContinuationToken is None

@pytest.mark.asyncio
async def test_list_objects_client_error(mock_boto3_session, mock_s3_settings):
    _, mock_client = mock_boto3_session
    service = S3Service(settings=mock_s3_settings)
    mock_client.list_objects_v2.side_effect = ClientError({"Error": {"Code": "500"}}, "ListObjectsV2")
    
    with pytest.raises(ClientError):
        await service.list_objects("company1", "intent1")

@pytest.mark.asyncio
async def test_generate_presigned_url_success(mock_boto3_session, mock_s3_settings):
    _, mock_client = mock_boto3_session
    service = S3Service(settings=mock_s3_settings)
    service.exists = AsyncMock(return_value=True) # Mock exists to return True
    mock_client.generate_presigned_url.return_value = "http://presigned.url/test-key"
    
    url = await service.generate_presigned_url("test-key", expiration=600)
    
    assert url == "http://presigned.url/test-key"
    service.exists.assert_called_once_with("test-key")
    mock_client.generate_presigned_url.assert_called_once_with(
        "get_object", Params={"Bucket": "test-bucket", "Key": "test-key"}, ExpiresIn=600
    )

@pytest.mark.asyncio
async def test_generate_presigned_url_object_not_found(mock_boto3_session, mock_s3_settings):
    _, mock_client = mock_boto3_session
    service = S3Service(settings=mock_s3_settings)
    service.exists = AsyncMock(return_value=False) # Mock exists to return False
    
    with pytest.raises(ValueError, match="Object not found: non-existent-key"):
        await service.generate_presigned_url("non-existent-key")
    
    service.exists.assert_called_once_with("non-existent-key")
    mock_client.generate_presigned_url.assert_not_called()

@pytest.mark.asyncio
async def test_generate_presigned_url_client_error(mock_boto3_session, mock_s3_settings):
    _, mock_client = mock_boto3_session
    service = S3Service(settings=mock_s3_settings)
    service.exists = AsyncMock(return_value=True) # Mock exists to return True
    mock_client.generate_presigned_url.side_effect = ClientError({"Error": {"Code": "500"}}, "GetObject")
    
    with pytest.raises(ClientError):
        await service.generate_presigned_url("error-key")
    
    service.exists.assert_called_once_with("error-key")