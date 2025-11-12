#!/bin/bash
set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REGION="ap-southeast-2"
PROFILE="cohesv"
ACCOUNT_ID="404293832854"

# Usage
usage() {
    cat <<EOF
Usage: $0 <environment> <stack> [options]

Deploy CloudFormation stacks for AI Voice Tool infrastructure.

Arguments:
  environment   Environment name (dev, staging, prod)
  stack         Stack to deploy:
                  - ecr              ECR repositories (deploy first)
                  - shared           Shared infrastructure (S3, SQS, API Gateway)
                  - customer-lookup  Customer lookup Lambda
                  - voice-parser     Voice parser Lambda
                  - webhook-handler  Webhook handler Lambda
                  - data-api         Data API Lambda
                  - all              Deploy all stacks in order

Options:
  --region REGION      AWS region (default: ap-southeast-2)
  --profile PROFILE    AWS profile (default: cohesv)
  --no-execute         Create change set but don't execute
  --help               Show this help message

Examples:
  # Deploy ECR repositories for dev
  $0 dev ecr

  # Deploy all stacks for dev environment
  $0 dev all

  # Deploy shared infrastructure for prod
  $0 prod shared

  # Create change set without executing
  $0 dev voice-parser --no-execute

Before deploying:
  1. Ensure parameter files exist in infrastructure/parameters/
  2. Create secrets in AWS Secrets Manager (run: make secrets-create ENV=<env>)
  3. Build and push Docker images to ECR
  4. Get secret ARNs (run: make secrets-get-arns ENV=<env>)

EOF
    exit 1
}

# Parse arguments
ENV=""
STACK=""
NO_EXECUTE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --region)
            REGION="$2"
            shift 2
            ;;
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --no-execute)
            NO_EXECUTE="--no-execute-changeset"
            shift
            ;;
        --help)
            usage
            ;;
        *)
            if [[ -z "$ENV" ]]; then
                ENV="$1"
            elif [[ -z "$STACK" ]]; then
                STACK="$1"
            else
                echo -e "${RED}Error: Unexpected argument '$1'${NC}"
                usage
            fi
            shift
            ;;
    esac
done

# Validate arguments
if [[ -z "$ENV" ]] || [[ -z "$STACK" ]]; then
    echo -e "${RED}Error: Missing required arguments${NC}"
    usage
fi

# Validate environment
if [[ ! -f "infrastructure/parameters/${ENV}.json" ]]; then
    echo -e "${RED}Error: Parameter file not found: infrastructure/parameters/${ENV}.json${NC}"
    exit 1
fi

# Helper function to deploy a stack
deploy_stack() {
    local stack_name=$1
    local template_file=$2
    local extra_params=$3

    echo -e "${GREEN}Deploying ${stack_name}...${NC}"

    # Convert JSON parameter file into Key=Value overrides
    local param_file="infrastructure/parameters/${ENV}.json"
    if ! command -v jq >/dev/null 2>&1; then
        echo -e "${RED}Error: jq is required to parse ${param_file}${NC}"
        exit 1
    fi

    mapfile -t base_params < <(jq -r '.[] | "\(.ParameterKey)=\(.ParameterValue)"' "$param_file")
    local params=("${base_params[@]}")

    # Add extra parameters if provided
    if [[ -n "$extra_params" ]]; then
        read -r -a extra_array <<< "$extra_params"
        params+=("${extra_array[@]}")
    fi

    aws cloudformation deploy \
        --region "$REGION" \
        --profile "$PROFILE" \
        --stack-name "${ENV}-${stack_name}" \
        --template-file "$template_file" \
        --capabilities CAPABILITY_NAMED_IAM \
        --parameter-overrides "${params[@]}" \
        $NO_EXECUTE

    if [[ -z "$NO_EXECUTE" ]]; then
        echo -e "${GREEN}✓ ${stack_name} deployed successfully${NC}\n"
    else
        echo -e "${YELLOW}✓ Change set created for ${stack_name} (not executed)${NC}\n"
    fi
}

# Helper function to get secret ARNs
get_secret_arn() {
    local secret_name=$1
    aws secretsmanager describe-secret \
        --region "$REGION" \
        --profile "$PROFILE" \
        --secret-id "$secret_name" \
        --query 'ARN' \
        --output text 2>/dev/null || echo ""
}

# Deploy ECR stack
deploy_ecr() {
    deploy_stack "ai-voice-ecr" "infrastructure/ecr/template.yaml"
}

# Deploy shared infrastructure
deploy_shared() {
    # Check if data-api-authorizer image exists in ECR (required by shared stack)
    local repo_uri="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/ai-voice-tool/${ENV}/data-api-authorizer:latest"

    echo -e "${YELLOW}Checking if data-api-authorizer image exists in ECR...${NC}"
    if ! aws ecr describe-images \
        --region "$REGION" \
        --profile "$PROFILE" \
        --repository-name "ai-voice-tool/${ENV}/data-api-authorizer" \
        --image-ids imageTag=latest \
        >/dev/null 2>&1; then
        echo -e "${RED}Error: data-api-authorizer image not found in ECR${NC}"
        echo "Run: make push-data-api-authorizer ENV=${ENV}"
        exit 1
    fi
    echo -e "${GREEN}✓ Authorizer image found${NC}"

    deploy_stack "ai-voice-shared" "infrastructure/shared/template.yaml"
}

# Deploy customer lookup
deploy_customer_lookup() {
    local repo_uri="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/ai-voice-tool/${ENV}/customer-lookup:latest"

    deploy_stack "ai-voice-customer-lookup" \
        "infrastructure/customer-lookup-server/template.yaml" \
        "LambdaImageUri=${repo_uri}"
}

# Deploy voice parser
deploy_voice_parser() {
    local repo_uri="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/ai-voice-tool/${ENV}/voice-parser:latest"

    # Get secret ARNs
    local twilio_sid_secret_arn=$(get_secret_arn "${ENV}/twilio/account-sid")
    local twilio_auth_secret_arn=$(get_secret_arn "${ENV}/twilio/auth-token")
    local openai_secret_arn=$(get_secret_arn "${ENV}/openai/api-key")

    if [[ -z "$twilio_sid_secret_arn" ]] || [[ -z "$twilio_auth_secret_arn" ]] || [[ -z "$openai_secret_arn" ]]; then
        echo -e "${RED}Error: Secrets not found in AWS Secrets Manager${NC}"
        echo "Run: make secrets-create ENV=${ENV}"
        exit 1
    fi

    deploy_stack "ai-voice-parser" \
        "infrastructure/voice-parser/template.yaml" \
        "LambdaImageUri=${repo_uri} TwilioAccountSidSecretArn=${twilio_sid_secret_arn} TwilioAuthTokenSecretArn=${twilio_auth_secret_arn} OpenAIApiKeySecretArn=${openai_secret_arn}"
}

# Deploy webhook handler
deploy_webhook_handler() {
    local repo_uri="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/ai-voice-tool/${ENV}/webhook-handler:latest"

    # Get secret ARN
    local twilio_secret_arn=$(get_secret_arn "${ENV}/twilio/auth-token")

    if [[ -z "$twilio_secret_arn" ]]; then
        echo -e "${RED}Error: Twilio secret not found in AWS Secrets Manager${NC}"
        echo "Run: make secrets-create ENV=${ENV}"
        exit 1
    fi

    deploy_stack "ai-voice-webhook" \
        "infrastructure/webhook-handler/template.yaml" \
        "LambdaImageUri=${repo_uri} TwilioAuthTokenSecretArn=${twilio_secret_arn}"
}

# Deploy data API
deploy_data_api() {
    local repo_uri="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/ai-voice-tool/${ENV}/data-api:latest"

    deploy_stack "ai-voice-data-api" \
        "infrastructure/data-api-server/template.yaml" \
        "LambdaImageUri=${repo_uri}"
}

# Deploy all stacks in order
deploy_all() {
    echo -e "${YELLOW}Deploying all stacks for environment: ${ENV}${NC}\n"

    echo -e "${YELLOW}Note: Ensure all Docker images are built and pushed to ECR before deploying${NC}"
    echo -e "${YELLOW}Run: make push-images ENV=${ENV}${NC}\n"

    deploy_ecr
    deploy_shared
    deploy_customer_lookup
    deploy_voice_parser
    deploy_webhook_handler
    deploy_data_api

    echo -e "${GREEN}✓ All stacks deployed successfully!${NC}"
}

# Main deployment logic
case $STACK in
    ecr)
        deploy_ecr
        ;;
    shared)
        deploy_shared
        ;;
    customer-lookup)
        deploy_customer_lookup
        ;;
    voice-parser)
        deploy_voice_parser
        ;;
    webhook-handler)
        deploy_webhook_handler
        ;;
    data-api)
        deploy_data_api
        ;;
    all)
        deploy_all
        ;;
    *)
        echo -e "${RED}Error: Unknown stack '${STACK}'${NC}"
        usage
        ;;
esac
