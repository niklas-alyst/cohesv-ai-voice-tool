# AI Voice Tool CloudFormation Stacks

This directory contains CloudFormation templates that codify the shared cloud infrastructure and the four Lambda-based microservices that compose the AI Voice Tool platform. Deploy the stacks in the order below so that cross-stack references resolve correctly.

## Deployment order

1. `ecr/template.yaml` &mdash; creates ECR repositories for all four microservice container images with lifecycle policies.
2. `shared/template.yaml` &mdash; creates the shared S3 bucket, SQS queue (plus DLQ), and two HTTP API Gateway instances (one for the Twilio webhook, one for the data API).
3. `customer-lookup-server/template.yaml` &mdash; container-based Lambda that reads customer data from the shared bucket.
4. `voice-parser/template.yaml` &mdash; SQS-triggered worker that writes artifacts to the shared bucket and invokes the lookup Lambda.
5. `webhook-handler/template.yaml` &mdash; API Gateway backed Lambda that validates Twilio webhooks and publishes messages to SQS.
6. `data-api-server/template.yaml` &mdash; API Gateway backed FastAPI Lambda that exposes read access to the shared bucket.

Each stack exports ARNs, names, and URLs using `${EnvironmentName}-`-prefixed export names so other stacks can import them.

## Parameter Configuration

Infrastructure parameters are stored in environment-specific JSON files under `parameters/`:
- `parameters/dev.json` - Development environment
- `parameters/prod.json` - Production environment

These files contain non-secret configuration like bucket names, Twilio account SIDs, and environment identifiers. See [parameters/README.md](parameters/README.md) for details.

Secret values (API keys, auth tokens) are managed separately via AWS Secrets Manager. See [SECRETS.md](SECRETS.md) for secrets management.

## Parameters quick reference

### ECR stack (`ecr/template.yaml`)
- `EnvironmentName` &mdash; identifier used to namespace repositories (e.g. `dev`, `staging`, `prod`).

### Shared stack (`shared/template.yaml`)
- `EnvironmentName` &mdash; identifier used to namespace resources and export names (e.g. `dev`, `staging`, `prod`).
- `VoiceDataBucketName` &mdash; globally-unique S3 bucket name used by every service (e.g. `cohesv-ai-voice-tool-dev`).

### Customer lookup (`customer-lookup-server/template.yaml`)
- `EnvironmentName`
- `LambdaImageUri` &mdash; ECR image URI for the containerised Lambda.
- `LambdaTimeoutSeconds` (default 30).
- `CustomerDataKey` (default `customers.json`).

### Voice parser (`voice-parser/template.yaml`)
- `EnvironmentName`
- `LambdaImageUri`
- `LambdaTimeoutSeconds` (default 900).
- `LambdaMemorySize` (default 1024 MB).
- `TwilioWhatsappNumber`.
- `TwilioAccountSid`, `TwilioAuthTokenSecretArn`, `OpenAIApiKeySecretArn` &mdash; Secrets Manager ARNs resolved into environment variables.

### Webhook handler (`webhook-handler/template.yaml`)
- `EnvironmentName`
- `LambdaImageUri`
- `LambdaTimeoutSeconds` (default 30).
- `LambdaMemorySize` (default 512 MB).
- `TwilioAuthTokenSecretArn`.

### Data API (`data-api-server/template.yaml`)
- `EnvironmentName`
- `LambdaImageUri`
- `LambdaTimeoutSeconds` (default 30).
- `LambdaMemorySize` (default 512 MB).

## Quick Start Deployment

### Prerequisites

1. **Create secrets in AWS Secrets Manager:**
   ```bash
   # Create .env files from examples
   cp webhook-handler/.env.example webhook-handler/.env
   cp voice-parser/.env.example voice-parser/.env

   # Edit .env files and add actual secret values
   # Then create secrets in AWS Secrets Manager
   make secrets-create ENV=dev
   ```

2. **Update parameter files:**
   Edit `infrastructure/parameters/dev.json` with your environment-specific values (bucket names, Twilio account SID, etc.)

### Deployment Methods

#### Option 1: Using the deployment script

```bash
# Deploy all stacks for dev environment
./infrastructure/deploy.sh dev all

# Or deploy individual stacks
./infrastructure/deploy.sh dev ecr
./infrastructure/deploy.sh dev shared
./infrastructure/deploy.sh dev customer-lookup
./infrastructure/deploy.sh dev voice-parser
./infrastructure/deploy.sh dev webhook-handler
./infrastructure/deploy.sh dev data-api
```

#### Option 2: Manual deployment with AWS CLI

```bash
ENV=dev
REGION=ap-southeast-2
ACCOUNT_ID=404293832854
PARAM_OVERRIDES=$(jq -r '.[] | "\(.ParameterKey)=\(.ParameterValue)"' infrastructure/parameters/$ENV.json)

# 1. ECR repositories
aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$ENV-ai-voice-ecr" \
  --template-file infrastructure/ecr/template.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides $PARAM_OVERRIDES

# 2. Shared resources
aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$ENV-ai-voice-shared" \
  --template-file infrastructure/shared/template.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides $PARAM_OVERRIDES

# 3. Build and push Docker images
make build-customer-lookup
docker tag customer-lookup-server:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/ai-voice-tool/$ENV/customer-lookup:latest
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/ai-voice-tool/$ENV/customer-lookup:latest

# Repeat for other services...

# 4. Customer lookup Lambda
aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$ENV-ai-voice-customer-lookup" \
  --template-file infrastructure/customer-lookup-server/template.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    $PARAM_OVERRIDES \
    LambdaImageUri=$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/ai-voice-tool/$ENV/customer-lookup:latest

# 5-7. Deploy remaining Lambda stacks (voice-parser, webhook-handler, data-api)
# See deploy.sh for complete examples with secret ARNs
```

_Note: the manual commands above rely on `jq` to translate the JSON parameter file into `Key=Value` overrides._

## Secrets Management

Before deploying Lambda stacks, you must create secrets in AWS Secrets Manager. See [SECRETS.md](./SECRETS.md) for detailed instructions.

**Quick reference:**
```bash
# Create secrets
make secrets-create ENV=dev

# Get secret ARNs for deployment
make secrets-get-arns ENV=dev
```

## ECR Repository Structure

ECR repositories are namespaced by environment for isolation:
- `ai-voice-tool/dev/voice-parser`
- `ai-voice-tool/dev/webhook-handler`
- `ai-voice-tool/dev/customer-lookup`
- `ai-voice-tool/dev/data-api`

Each repository has:
- **Image scanning** enabled on push for vulnerability detection
- **Encryption** using AWS-managed keys (AES256)
- **Lifecycle policies** that:
  - Keep the last 5 tagged images (latest, v*)
  - Expire untagged images older than 7 days

## Building and Pushing Images

After deploying the ECR stack, build and push images:

```bash
ENV=dev
REGION=ap-southeast-2
ACCOUNT_ID=404293832854

# Authenticate with ECR
aws ecr get-login-password --region $REGION --profile cohesv | \
  docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

# Build and push voice-parser
docker build -f voice-parser/Dockerfile -t voice-parser:latest .
docker tag voice-parser:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/ai-voice-tool/$ENV/voice-parser:latest
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/ai-voice-tool/$ENV/voice-parser:latest

# Repeat for other services...
```

Or use the Makefile (note: Makefile uses the old non-environment-namespaced ECR structure and needs updating):
```bash
make build-voice-parser
make deploy-voice-parser
```

## Additional notes

- **ECR repositories must be deployed first** before building/pushing images
- **Parameter files** (`parameters/*.json`) store non-secret configuration and are safe to commit
- The HTTP API endpoints exported by the shared stack are base URLs; append `/webhook` to reach endpoints (e.g. `https://abc123.execute-api.ap-southeast-2.amazonaws.com/dev/webhook`)
- Secrets Manager dynamic references (`{{resolve:secretsmanager:...}}`) are resolved at deploy time so the actual secret values are injected into Lambda environment variables
- To rotate secrets: update in Secrets Manager, then redeploy affected Lambda stacks
- The deployment script automatically retrieves secret ARNs from Secrets Manager
