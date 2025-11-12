# End-to-End Tests

End-to-end tests for the AI Voice Tool that validate the complete message processing pipeline against the deployed AWS infrastructure.

## Overview

These tests execute the full workflow:
1. POST webhook with valid Twilio signature → API Gateway → webhook-handler Lambda
2. webhook-handler validates and enqueues to SQS
3. voice-parser Lambda processes from SQS
4. Files uploaded to S3
5. Data API retrieval tested
6. Cleanup of test artifacts

**Important**: These tests hit real AWS services (Lambda, SQS, S3) and external APIs (OpenAI for transcription/LLM). They are:
- **Slow** (30-90 seconds per test)
- **Expensive** (~$0.05-0.10 per test due to OpenAI API calls)
- **Stateful** (create real data in S3)

Run these tests sparingly - they are meant for deployment validation, not continuous integration.

## Prerequisites

1. **Deployed AWS Infrastructure**: Dev environment must be fully deployed
   ```bash
   ./infrastructure/deploy.sh dev all
   ```

2. **Python Dependencies**: Install test dependencies
   ```bash
   cd tests/e2e
   uv add --group dev pytest pytest-asyncio httpx boto3 python-dotenv
   ```

3. **AWS Credentials**: Configure AWS profile
   ```bash
   export AWS_PROFILE=cohesv
   ```

4. **Test Customer Data**: Upload test customer to S3
   ```bash
   AWS_PROFILE=cohesv aws s3 cp fixtures/test_customers.json \
     s3://cohesv-ai-voice-tool-dev/customers.json
   ```

   **Note**: This will overwrite your existing customers.json. For production use, merge the test customer into your existing customer list.

## Configuration

### 1. Get API Endpoints

Retrieve CloudFormation stack outputs:

```bash
# Get Webhook URL
AWS_PROFILE=cohesv aws cloudformation describe-stacks \
  --stack-name dev-ai-voice-shared \
  --region ap-southeast-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`WebhookApiUrl`].OutputValue' \
  --output text

# Get Data API URL
AWS_PROFILE=cohesv aws cloudformation describe-stacks \
  --stack-name dev-ai-voice-shared \
  --region ap-southeast-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`DataApiUrl`].OutputValue' \
  --output text
```

### 2. Get Secrets

Retrieve secrets from AWS Secrets Manager:

```bash
# Get Twilio Auth Token
AWS_PROFILE=cohesv aws secretsmanager get-secret-value \
  --secret-id dev/ai-voice-tool/twilio \
  --region ap-southeast-2 \
  --query SecretString \
  --output text | jq -r '.auth_token'

# Get Data API Key (if using API Gateway API keys)
# This depends on how you configured API Gateway authentication
```

### 3. Create Configuration File

```bash
cd tests/e2e
cp .env.e2e.example .env.e2e
```

Edit `.env.e2e` with the values retrieved above:

```bash
# AWS Configuration
AWS_REGION=ap-southeast-2
AWS_PROFILE=cohesv

# S3 Configuration
E2E_S3_BUCKET=cohesv-ai-voice-tool-dev

# API Endpoints (from CloudFormation outputs)
E2E_WEBHOOK_URL=https://YOUR_API_ID.execute-api.ap-southeast-2.amazonaws.com/webhook
E2E_DATA_API_URL=https://YOUR_API_ID.execute-api.ap-southeast-2.amazonaws.com
E2E_DATA_API_KEY=your-data-api-key-here

# Twilio Configuration (from Secrets Manager)
TWILIO_AUTH_TOKEN=your-twilio-auth-token-here
TWILIO_ACCOUNT_SID=AC1234567890abcdef1234567890abcdef
TWILIO_WHATSAPP_NUMBER=whatsapp:+61468035449

# Test Customer Configuration (matches fixtures/test_customers.json)
E2E_TEST_COMPANY_ID=test-company-e2e
E2E_TEST_CUSTOMER_ID=test-customer-e2e
E2E_TEST_PHONE_NUMBER=whatsapp:+15555555555

# Test Configuration
E2E_TEST_TIMEOUT_SECONDS=90
E2E_CLEANUP_ON_FAILURE=true
```

## Running Tests

### Run All E2E Tests

```bash
cd /home/niklas/code/cohesv/ai-voice-tool
uv run pytest tests/e2e/ -m e2e -v -s
```

### Run Specific Test

```bash
# Text message test only
uv run pytest tests/e2e/test_text_message_e2e.py -v -s

# Voice message test only (requires E2E_TEST_AUDIO_MEDIA_URL)
uv run pytest tests/e2e/test_voice_message_e2e.py -v -s
```

### Exclude E2E Tests from Regular Runs

E2E tests are marked with `@pytest.mark.e2e`. To run all tests EXCEPT E2E:

```bash
uv run pytest -m "not e2e"
```

## Test Structure

```
tests/e2e/
├── README.md                      # This file
├── .env.e2e.example              # Configuration template
├── .env.e2e                      # Your configuration (gitignored)
├── conftest.py                   # Shared fixtures and pytest config
├── test_text_message_e2e.py     # Text message full pipeline test
├── test_voice_message_e2e.py    # Voice message full pipeline test
├── fixtures/
│   ├── test_audio.ogg           # Test audio file
│   └── test_customers.json      # Test customer data
└── utils/
    ├── twilio_signature.py      # Twilio signature generation
    └── s3_helpers.py            # S3 polling and cleanup utilities
```

## Test Details

### test_text_message_e2e.py

Tests complete text message processing:
- ✅ Webhook signature validation
- ✅ Customer authorization via customer-lookup-server
- ✅ SQS enqueueing
- ✅ Async processing by voice-parser
- ✅ LLM intent classification
- ✅ LLM content structuring
- ✅ S3 file upload (full_text.txt, text_summary.txt)
- ✅ Data API file listing
- ✅ Presigned URL generation and download
- ✅ Cleanup

**Duration**: ~30-60 seconds

### test_voice_message_e2e.py

Tests complete voice message processing:
- ✅ All text message steps, plus:
- ✅ Audio download from Twilio
- ✅ OpenAI Whisper transcription
- ✅ S3 audio file upload (audio.ogg)

**Duration**: ~60-90 seconds (transcription is slow)

**Note**: Requires `E2E_TEST_AUDIO_MEDIA_URL` environment variable pointing to a publicly accessible audio file that the Lambda can download. This is a limitation of testing voice messages - the Lambda needs to download from a real URL.

## Voice Message Testing Limitation

The voice message test has a constraint: the `voice-parser` Lambda downloads audio from Twilio's media URL, which must be:
1. Publicly accessible
2. Authenticated with Twilio credentials
3. A real Twilio media URL or equivalent

**Options for voice testing:**

1. **Use Twilio Test Mode** (Recommended):
   - Upload test audio via Twilio API
   - Get a real media URL
   - Set `E2E_TEST_AUDIO_MEDIA_URL` env var

2. **Host Test Audio Publicly**:
   - Upload test_audio.ogg to a public URL
   - Set `E2E_TEST_AUDIO_MEDIA_URL` to that URL
   - Note: This bypasses Twilio auth testing

3. **Mock Twilio Endpoint**:
   - Deploy a mock HTTP server
   - Serve test audio at a public URL
   - More complex but allows full control

If `E2E_TEST_AUDIO_MEDIA_URL` is not set, the voice test will be skipped with a clear message.

## Cleanup

Tests automatically clean up their S3 artifacts after completion. You can also manually clean up:

```bash
# List test files
AWS_PROFILE=cohesv aws s3 ls s3://cohesv-ai-voice-tool-dev/test-company-e2e/ --recursive

# Delete all test files
AWS_PROFILE=cohesv aws s3 rm s3://cohesv-ai-voice-tool-dev/test-company-e2e/ --recursive
```

## Troubleshooting

### Test Timeout

If tests timeout waiting for S3 files:
1. Check Lambda execution in CloudWatch Logs
2. Verify SQS queue is being processed
3. Increase `E2E_TEST_TIMEOUT_SECONDS` in `.env.e2e`

```bash
# Check voice-parser logs
AWS_PROFILE=cohesv aws logs tail /aws/lambda/dev-ai-voice-voice-parser --follow --region ap-southeast-2

# Check webhook-handler logs
AWS_PROFILE=cohesv aws logs tail /aws/lambda/dev-ai-voice-webhook-handler --follow --region ap-southeast-2
```

### Invalid Signature

If webhook returns 403:
1. Verify `TWILIO_AUTH_TOKEN` matches deployed Lambda env var
2. Check `E2E_WEBHOOK_URL` is correct
3. Ensure URL includes protocol (https://)

### Customer Not Authorized

If webhook returns 403 with "Unauthorized sender":
1. Verify test customer was uploaded to S3
2. Check `E2E_TEST_PHONE_NUMBER` matches `fixtures/test_customers.json`
3. Confirm `customers.json` was uploaded to correct bucket

```bash
# Verify customer data in S3
AWS_PROFILE=cohesv aws s3 cp s3://cohesv-ai-voice-tool-dev/customers.json - | jq .
```

### S3 Permission Errors

If you see S3 access denied:
1. Verify AWS profile has S3 read/write permissions
2. Check bucket name matches deployed infrastructure
3. Ensure Lambda execution role has S3 permissions

### API Gateway 403

If Data API returns 403:
1. Verify `E2E_DATA_API_KEY` is correct
2. Check API Gateway has API key requirement configured
3. Confirm `x-api-key` header is being sent

## Cost Estimation

Each E2E test run costs approximately:

- **Lambda Invocations**: $0.0001 (negligible)
- **SQS Messages**: $0.0001 (negligible)
- **S3 Operations**: $0.001 (negligible)
- **OpenAI Whisper** (voice only): ~$0.006 per minute of audio
- **OpenAI GPT-4**: ~$0.01-0.05 per test (depends on prompt size)

**Total per test**: ~$0.05-0.10

For a full test suite run (2 tests): ~$0.10-0.20

## Best Practices

1. **Run Sparingly**: These are expensive integration tests - use for deployment validation, not every commit
2. **Check Logs First**: If a test fails, check CloudWatch logs before re-running
3. **Clean Up**: Tests auto-cleanup, but verify S3 if tests crash
4. **Isolate Test Data**: Always use separate test company IDs
5. **Monitor Costs**: Check AWS billing if running frequently
6. **Sequential Execution**: Don't run tests in parallel (they share S3 namespace)

## Adding New Tests

To add a new E2E test:

1. Create test file: `test_<scenario>_e2e.py`
2. Mark with `@pytest.mark.e2e`
3. Use fixtures from `conftest.py`
4. Follow the pattern: Setup → Act → Wait → Verify → Cleanup
5. Always clean up S3 artifacts in `finally` block
6. Add comprehensive logging for debugging

Example:

```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_my_scenario_e2e(e2e_config, s3_client, http_client, test_message_id):
    # Setup
    prefix = f"{e2e_config['test_company_id']}/"

    try:
        # Act
        # ... your test logic ...

        # Wait & Verify
        files = await wait_for_s3_files(...)
        assert len(files) > 0

    finally:
        # Cleanup
        await cleanup_s3_files(s3_client, e2e_config["s3_bucket"], prefix)
```

## Future Improvements

Potential enhancements:

1. **Parallel Test Execution**: Use unique S3 prefixes per test worker
2. **Mock External APIs**: Stub OpenAI/Twilio for faster, cheaper tests
3. **Test Fixtures API**: Create reusable test data management
4. **Performance Benchmarks**: Track processing time per message type
5. **Error Injection Tests**: Test failure scenarios (SQS failures, S3 errors)
6. **Load Testing**: Batch multiple messages to test throughput

## Support

For issues with E2E tests:
1. Check CloudWatch Logs for Lambda errors
2. Verify `.env.e2e` configuration
3. Ensure AWS infrastructure is deployed
4. Review this README for troubleshooting steps
