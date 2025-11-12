# CloudFormation Parameter Files

This directory contains environment-specific parameter files for CloudFormation deployments.

## Structure

- `dev.json` - Development environment parameters
- `prod.json` - Production environment parameters

## Parameter Categories

### Infrastructure Parameters (Non-Secret)
These parameters configure infrastructure settings and are stored in these JSON files:
- `EnvironmentName` - Environment identifier (dev, staging, prod)
- `VoiceDataBucketName` - S3 bucket name for voice data
- `TwilioWhatsappNumber` - WhatsApp phone number (format: whatsapp:+123456789)
- `CustomerDataKey` - S3 key for customer data file

### Secret Parameters
Secret parameters (API keys, auth tokens) are stored in AWS Secrets Manager and referenced by ARN:
- `TwilioAccountSidSecretArn` - ARN of Twilio account SID secret
- `TwilioAuthTokenSecretArn` - ARN of Twilio auth token secret
- `OpenAIApiKeySecretArn` - ARN of OpenAI API key secret

See [../SECRETS.md](../SECRETS.md) for secrets management instructions.

## Usage

Parameter files are used with the CloudFormation CLI or deployment scripts:

```bash
aws cloudformation deploy \
  --template-file infrastructure/shared/template.yaml \
  --stack-name dev-ai-voice-shared \
  --parameter-overrides $(jq -r '.[] | "\(.ParameterKey)=\(.ParameterValue)"' infrastructure/parameters/dev.json)

These examples assume `jq` is installed so the JSON parameter file can be converted into inline overrides that `aws cloudformation deploy` accepts.
```

Or with the deployment helper script:

```bash
./infrastructure/deploy.sh dev shared
```

## Adding New Environments

To add a new environment (e.g., staging):

1. Copy an existing parameter file:
   ```bash
   cp dev.json staging.json
   ```

2. Update the values:
   - Change `EnvironmentName` to `staging`
   - Update environment-specific values (bucket names, etc.)

3. Create corresponding secrets in AWS Secrets Manager:
   ```bash
   make secrets-create ENV=staging
   ```

4. Deploy the stacks with the new parameter file

## Security Notes

- These JSON files contain **non-secret** configuration only
- Never commit API keys, passwords, or auth tokens to these files
- Secret values are managed via AWS Secrets Manager (see SECRETS.md)
- The `.gitignore` is configured to allow committing these parameter files
