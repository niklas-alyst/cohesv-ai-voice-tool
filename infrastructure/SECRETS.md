# Secrets Management Guide

This guide explains how to manage secrets for the AI Voice Tool infrastructure using AWS Secrets Manager.

## Overview

Secrets (API keys, auth tokens) are stored in AWS Secrets Manager and injected into Lambda functions via CloudFormation dynamic references. Each microservice has a `.env.example` file showing which secrets it requires.

**Important:** Infrastructure parameters (Lambda function names, queue URLs, bucket names) are NOT secrets and are managed via CloudFormation parameters, not `.env` files.

## Setup Process

### 1. Create Local `.env` Files

Copy the `.env.example` files for services that require secrets:

```bash
# Webhook Handler (requires Twilio auth token)
cp webhook-handler/.env.example webhook-handler/.env

# Voice Parser (requires Twilio auth token and OpenAI API key)
cp voice-parser/.env.example voice-parser/.env
```

### 2. Fill in Secret Values

Edit the `.env` files and replace placeholder values with actual secrets:

**webhook-handler/.env:**
```bash
TWILIO_AUTH_TOKEN=your-actual-twilio-auth-token
```

**voice-parser/.env:**
```bash
TWILIO_ACCOUNT_SID=your-actual-twilio-account-sid
TWILIO_AUTH_TOKEN=your-actual-twilio-auth-token
OPENAI_API_KEY=sk-proj-your-actual-openai-api-key
```

**Note:** These `.env` files are gitignored and should NEVER be committed.

### 3. Create Secrets in AWS Secrets Manager

Use the Makefile commands to create secrets in AWS Secrets Manager:

```bash
# Create all secrets for dev environment (default)
make secrets-create

# Create secrets for a specific environment
make secrets-create ENV=staging
make secrets-create ENV=prod
```

This will create three secrets:
- `{ENV}/twilio/account-sid`
- `{ENV}/twilio/auth-token`
- `{ENV}/openai/api-key`

### 4. Get Secret ARNs for CloudFormation

After creating secrets, get their ARNs to use in CloudFormation deployments:

```bash
# Get ARNs for dev environment
make secrets-get-arns

# Get ARNs for specific environment
make secrets-get-arns ENV=prod
```

Example output:
```
Secret ARNs for environment: dev

TwilioAccountSidSecretArn:
arn:aws:secretsmanager:ap-southeast-2:404293832854:secret:dev/twilio/account-sid-abc123

TwilioAuthTokenSecretArn:
arn:aws:secretsmanager:ap-southeast-2:404293832854:secret:dev/twilio/auth-token-abc123

OpenAIApiKeySecretArn:
arn:aws:secretsmanager:ap-southeast-2:404293832854:secret:dev/openai/api-key-xyz789
```

Use these ARNs as CloudFormation parameters when deploying stacks.

## Updating Secrets

If you need to rotate or update secrets:

### 1. Update Local `.env` Files

Update the secret values in your `.env` files:

```bash
# Edit webhook-handler/.env and/or voice-parser/.env
vim webhook-handler/.env
vim voice-parser/.env
```

### 2. Update Secrets in AWS

```bash
# Update all secrets for dev environment
make secrets-update

# Update specific environment
make secrets-update ENV=prod
```

### 3. Redeploy Lambda Functions

After updating secrets, redeploy the affected Lambda functions for changes to take effect:

```bash
aws cloudformation deploy \
  --stack-name dev-ai-voice-webhook \
  --template-file infrastructure/webhook-handler/template.yaml \
  --no-execute-changeset
```

CloudFormation will show that environment variables have changed (due to dynamic secret resolution).

## Makefile Commands Reference

| Command | Description |
|---------|-------------|
| `make secrets-check` | Verify `.env` files exist and are properly configured |
| `make secrets-create` | Create all secrets in AWS Secrets Manager |
| `make secrets-create-twilio-auth-token` | Create only the Twilio auth token secret |
| `make secrets-create-openai-api-key` | Create only the OpenAI API key secret |
| `make secrets-update` | Update all existing secrets |
| `make secrets-update-twilio-auth-token` | Update only the Twilio auth token secret |
| `make secrets-update-openai-api-key` | Update only the OpenAI API key secret |
| `make secrets-get-arns` | Display ARNs for use in CloudFormation |

## Environment Variables

Commands accept an `ENV` variable to target different environments:

```bash
# Development (default)
make secrets-create ENV=dev

# Staging
make secrets-create ENV=staging

# Production
make secrets-create ENV=prod
```

## Security Best Practices

1. **Never commit `.env` files** - They are gitignored for security
2. **Rotate secrets regularly** - Use `make secrets-update` to rotate secrets
3. **Use environment-specific secrets** - Create separate secrets for dev/staging/prod
4. **Limit AWS IAM permissions** - Only grant necessary Secrets Manager permissions
5. **Monitor secret access** - Enable CloudTrail logging for Secrets Manager

## Troubleshooting

### Error: `.env` file not found

```bash
ERROR: webhook-handler/.env not found. Copy from .env.example and fill in values.
```

**Solution:** Create the `.env` file from the example:
```bash
cp webhook-handler/.env.example webhook-handler/.env
# Edit webhook-handler/.env and add actual secrets
```

### Error: Secret already exists

```bash
An error occurred (ResourceExistsException) when calling the CreateSecret operation:
The operation failed because the secret dev/twilio/auth-token already exists.
```

**Solution:** Use `make secrets-update` instead of `make secrets-create`.

### Error: Placeholder value detected

```bash
ERROR: TWILIO_AUTH_TOKEN not set in webhook-handler/.env or still has placeholder value
```

**Solution:** Replace placeholder values in `.env` files with actual secrets.

## CloudFormation Integration

The CloudFormation templates use dynamic secret references:

```yaml
Environment:
  Variables:
    TWILIO_AUTH_TOKEN: !Sub '{{resolve:secretsmanager:${TwilioAuthTokenSecretArn}:SecretString}}'
```

This resolves the secret at deployment time, injecting the actual value into the Lambda environment variables.

## Services Without Secrets

Some services don't require secrets:
- **customer-lookup-server** - Only reads from S3 (no API keys needed)
- **data-api-server** - Only reads from S3 (no API keys needed)

These services still have `.env.example` files (marked as "no secrets required") for consistency.
