#!/bin/bash
# Setup script for E2E tests
# This script helps configure the E2E test environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== AI Voice Tool E2E Test Setup ==="
echo ""

# Check if .env.e2e exists
if [ -f "$SCRIPT_DIR/.env.e2e" ]; then
    echo "✓ .env.e2e already exists"
    read -p "Do you want to regenerate it? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping .env.e2e creation"
    else
        cp "$SCRIPT_DIR/.env.e2e.example" "$SCRIPT_DIR/.env.e2e"
        echo "✓ Created .env.e2e from template"
    fi
else
    cp "$SCRIPT_DIR/.env.e2e.example" "$SCRIPT_DIR/.env.e2e"
    echo "✓ Created .env.e2e from template"
fi

echo ""
echo "=== Retrieving CloudFormation Outputs ==="

# Get AWS profile
AWS_PROFILE=${AWS_PROFILE:-cohesv}
AWS_REGION=${AWS_REGION:-ap-southeast-2}
ENV=${ENV:-dev}

echo "Using AWS Profile: $AWS_PROFILE"
echo "Using AWS Region: $AWS_REGION"
echo "Using Environment: $ENV"
echo ""

# Get Webhook URL
echo "Fetching Webhook API URL..."
WEBHOOK_URL=$(aws cloudformation describe-stacks \
    --stack-name "${ENV}-ai-voice-shared" \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE" \
    --query 'Stacks[0].Outputs[?OutputKey==`WebhookApiUrl`].OutputValue' \
    --output text 2>/dev/null || echo "")

if [ -n "$WEBHOOK_URL" ]; then
    echo "✓ Webhook URL: $WEBHOOK_URL"
    sed -i "s|E2E_WEBHOOK_URL=.*|E2E_WEBHOOK_URL=$WEBHOOK_URL|g" "$SCRIPT_DIR/.env.e2e"
else
    echo "⚠ Could not retrieve Webhook URL from CloudFormation"
fi

# Get Data API URL
echo "Fetching Data API URL..."
DATA_API_URL=$(aws cloudformation describe-stacks \
    --stack-name "${ENV}-ai-voice-shared" \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE" \
    --query 'Stacks[0].Outputs[?OutputKey==`DataApiUrl`].OutputValue' \
    --output text 2>/dev/null || echo "")

if [ -n "$DATA_API_URL" ]; then
    echo "✓ Data API URL: $DATA_API_URL"
    sed -i "s|E2E_DATA_API_URL=.*|E2E_DATA_API_URL=$DATA_API_URL|g" "$SCRIPT_DIR/.env.e2e"
else
    echo "⚠ Could not retrieve Data API URL from CloudFormation"
fi

# Get S3 Bucket
echo "Fetching S3 Bucket..."
S3_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name "${ENV}-ai-voice-shared" \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE" \
    --query 'Stacks[0].Outputs[?OutputKey==`VoiceDataBucketName`].OutputValue' \
    --output text 2>/dev/null || echo "")

if [ -n "$S3_BUCKET" ]; then
    echo "✓ S3 Bucket: $S3_BUCKET"
    sed -i "s|E2E_S3_BUCKET=.*|E2E_S3_BUCKET=$S3_BUCKET|g" "$SCRIPT_DIR/.env.e2e"
else
    echo "⚠ Could not retrieve S3 Bucket from CloudFormation"
fi

echo ""
echo "=== Retrieving Secrets ==="

# Get Twilio Auth Token
echo "Fetching Twilio credentials from Secrets Manager..."
TWILIO_SECRET=$(aws secretsmanager get-secret-value \
    --secret-id "${ENV}/ai-voice-tool/twilio" \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE" \
    --query 'SecretString' \
    --output text 2>/dev/null || echo "")

if [ -n "$TWILIO_SECRET" ]; then
    TWILIO_AUTH_TOKEN=$(echo "$TWILIO_SECRET" | jq -r '.auth_token')
    TWILIO_ACCOUNT_SID=$(echo "$TWILIO_SECRET" | jq -r '.account_sid')

    if [ "$TWILIO_AUTH_TOKEN" != "null" ]; then
        echo "✓ Twilio Auth Token retrieved"
        sed -i "s|TWILIO_AUTH_TOKEN=.*|TWILIO_AUTH_TOKEN=$TWILIO_AUTH_TOKEN|g" "$SCRIPT_DIR/.env.e2e"
    fi

    if [ "$TWILIO_ACCOUNT_SID" != "null" ]; then
        echo "✓ Twilio Account SID: $TWILIO_ACCOUNT_SID"
        sed -i "s|TWILIO_ACCOUNT_SID=.*|TWILIO_ACCOUNT_SID=$TWILIO_ACCOUNT_SID|g" "$SCRIPT_DIR/.env.e2e"
    fi
else
    echo "⚠ Could not retrieve Twilio secrets from Secrets Manager"
fi

echo ""
echo "=== Upload Test Customer Data ==="
echo ""
read -p "Upload test customer data to S3? This will OVERWRITE customers.json. (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -n "$S3_BUCKET" ]; then
        aws s3 cp "$SCRIPT_DIR/fixtures/test_customers.json" \
            "s3://$S3_BUCKET/customers.json" \
            --profile "$AWS_PROFILE" \
            --region "$AWS_REGION"
        echo "✓ Test customer data uploaded"
    else
        echo "⚠ S3 bucket not configured, skipping upload"
    fi
else
    echo "Skipped customer data upload"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Review and edit .env.e2e with any missing values"
echo "2. Add the Data API key manually (E2E_DATA_API_KEY)"
echo "3. Run tests: cd $PROJECT_ROOT && uv run pytest tests/e2e/ -m e2e -v -s"
echo ""
echo "See tests/e2e/README.md for detailed instructions"
