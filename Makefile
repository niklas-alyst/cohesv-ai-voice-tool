# AI Voice Tool - Makefile
#
# This Makefile handles Docker image building/pushing and infrastructure deployment.
#
# Common workflows (recommended order):
#
#   QUALITY GATES:
#     make lint                     # Run linting on all services
#     make test                     # Run all tests
#
#   SECRETS MANAGEMENT:
#     make secrets-create ENV=dev   # Create secrets in AWS Secrets Manager
#     make secrets-update ENV=dev   # Update existing secrets
#     make secrets-get-arns ENV=dev # Get ARNs for CloudFormation parameters
#
#   DOCKER IMAGES:
#     make build                    # Build all Docker images locally
#     make push-images              # Build and push all images to ECR
#     make push-voice-parser        # Build and push just voice-parser image
#     make push ENV=prod            # Push images to prod ECR repositories
#
#   INFRASTRUCTURE DEPLOYMENT (via CloudFormation):
#     make deploy-infra             # Deploy all infrastructure stacks
#     make deploy-ecr               # Deploy ECR repositories only
#     make deploy-shared            # Deploy shared resources (S3, SQS, API Gateway)
#     make deploy-voice-parser      # Push image + deploy voice-parser Lambda
#     make deploy-webhook-handler   # Push image + deploy webhook-handler Lambda
#     make deploy-customer-lookup   # Push image + deploy customer-lookup Lambda
#     make deploy-data-api          # Push image + deploy data-api Lambda
#     make deploy ENV=prod          # Deploy to production environment

# Variables
ECR_REGISTRY := 404293832854.dkr.ecr.ap-southeast-2.amazonaws.com
REGION := ap-southeast-2
PROFILE := cohesv
TAG := latest

# Environment (can be overridden: make push ENV=prod)
ENV ?= dev

# Service Repositories (environment-namespaced)
VOICE_PARSER_REPO := $(ECR_REGISTRY)/ai-voice-tool/$(ENV)/voice-parser
WEBHOOK_HANDLER_REPO := $(ECR_REGISTRY)/ai-voice-tool/$(ENV)/webhook-handler
CUSTOMER_LOOKUP_REPO := $(ECR_REGISTRY)/ai-voice-tool/$(ENV)/customer-lookup
DATA_API_REPO := $(ECR_REGISTRY)/ai-voice-tool/$(ENV)/data-api

# Image Names
VOICE_PARSER_IMG := voice-parser
WEBHOOK_HANDLER_IMG := webhook-handler
CUSTOMER_LOOKUP_IMG := customer-lookup-server
DATA_API_IMG := data-api-server

.PHONY: all build push-images ecr-login \
	build-voice-parser push-voice-parser deploy-voice-parser \
	build-webhook-handler push-webhook-handler deploy-webhook-handler \
	build-customer-lookup push-customer-lookup deploy-customer-lookup \
	build-data-api push-data-api deploy-data-api \
	deploy-infra deploy-ecr deploy-shared \
	install-shared-lib install-shared-lib-voice-parser install-shared-lib-webhook-handler \
	lint lint-voice-parser lint-webhook-handler lint-shared-lib lint-customer-lookup lint-data-api \
	test test-voice-parser test-webhook-handler test-shared-lib test-customer-lookup test-data-api

all: build
lint: lint-voice-parser lint-webhook-handler lint-shared-lib lint-customer-lookup lint-data-api
test: test-voice-parser test-webhook-handler test-shared-lib test-customer-lookup test-data-api
build: build-voice-parser build-webhook-handler build-customer-lookup build-data-api
push-images: push-voice-parser push-webhook-handler push-customer-lookup push-data-api
deploy-infra: deploy-ecr deploy-shared deploy-customer-lookup deploy-voice-parser deploy-webhook-handler deploy-data-api

# --- ECR Login ---
ecr-login:
	@echo "Logging in to ECR..."
	@aws ecr get-login-password --region $(REGION) --profile $(PROFILE) | \
		docker login --username AWS --password-stdin $(ECR_REGISTRY)

# --- Shared Library (Local Development) ---
install-shared-lib-voice-parser:
	cd voice-parser && uv add --editable ../shared-lib

install-shared-lib-webhook-handler:
	cd webhook-handler && uv add --editable ../shared-lib

install-shared-lib: install-shared-lib-voice-parser install-shared-lib-webhook-handler

# --- Linting ---
lint-voice-parser:
	cd voice-parser && uv run ruff check --fix

lint-webhook-handler:
	cd webhook-handler && uv run ruff check --fix

lint-shared-lib:
	cd shared-lib && uv run ruff check --fix

lint-customer-lookup:
	cd customer-lookup-server && uv run ruff check --fix

lint-data-api:
	cd data-api-server && uv run ruff check --fix

# --- Testing ---
test-voice-parser:
	cd voice-parser && uv run pytest tests

test-webhook-handler:
	cd webhook-handler && uv run pytest tests

test-shared-lib:
	cd shared-lib && uv run pytest tests

test-customer-lookup:
	cd customer-lookup-server && uv run pytest tests

test-data-api:
	cd data-api-server && uv run pytest tests


# --- Secrets Management ---
# Note: ENV variable is defined at the top of the Makefile

# Check that required .env files exist before creating secrets
secrets-check:
	@echo "Checking for .env files..."
	@test -f webhook-handler/.env || (echo "ERROR: webhook-handler/.env not found. Copy from .env.example and fill in values." && exit 1)
	@test -f voice-parser/.env || (echo "ERROR: voice-parser/.env not found. Copy from .env.example and fill in values." && exit 1)
	@echo "✓ All required .env files found"

# Create Twilio Account SID secret in AWS Secrets Manager
secrets-create-twilio-account-sid: secrets-check
	@echo "Creating Twilio Account SID secret for environment: $(ENV)"
	@TWILIO_ACCOUNT_SID=$$(grep -E '^TWILIO_ACCOUNT_SID=' webhook-handler/.env | cut -d '=' -f2-); \
	if [ -z "$$TWILIO_ACCOUNT_SID" ] || [ "$$TWILIO_ACCOUNT_SID" = "your-twilio-account-sid" ]; then \
		echo "ERROR: TWILIO_ACCOUNT_SID not set in webhook-handler/.env or still has placeholder value"; \
		exit 1; \
	fi; \
	aws secretsmanager create-secret \
		--region $(REGION) \
		--profile $(PROFILE) \
		--name "$(ENV)/twilio/account-sid" \
		--description "Twilio Auth Token for $(ENV) environment" \
		--secret-string "$$TWILIO_ACCOUNT_SID" \
		--tags Key=Environment,Value=$(ENV) Key=Service,Value=ai-voice-tool
	@echo "✓ Twilio Account SID secret created: $(ENV)/twilio/account-sid"

# Create Twilio Auth Token secret in AWS Secrets Manager
secrets-create-twilio-auth-token: secrets-check
	@echo "Creating Twilio Auth Token secret for environment: $(ENV)"
	@TWILIO_AUTH_TOKEN=$$(grep -E '^TWILIO_AUTH_TOKEN=' webhook-handler/.env | cut -d '=' -f2-); \
	if [ -z "$$TWILIO_AUTH_TOKEN" ] || [ "$$TWILIO_AUTH_TOKEN" = "your-twilio-auth-token-here" ]; then \
		echo "ERROR: TWILIO_AUTH_TOKEN not set in webhook-handler/.env or still has placeholder value"; \
		exit 1; \
	fi; \
	aws secretsmanager create-secret \
		--region $(REGION) \
		--profile $(PROFILE) \
		--name "$(ENV)/twilio/auth-token" \
		--description "Twilio Auth Token for $(ENV) environment" \
		--secret-string "$$TWILIO_AUTH_TOKEN" \
		--tags Key=Environment,Value=$(ENV) Key=Service,Value=ai-voice-tool
	@echo "✓ Twilio Auth Token secret created: $(ENV)/twilio/auth-token"

# Create OpenAI API Key secret in AWS Secrets Manager
secrets-create-openai-api-key: secrets-check
	@echo "Creating OpenAI API Key secret for environment: $(ENV)"
	@OPENAI_API_KEY=$$(grep -E '^OPENAI_API_KEY=' voice-parser/.env | cut -d '=' -f2-); \
	if [ -z "$$OPENAI_API_KEY" ] || [ "$$OPENAI_API_KEY" = "sk-proj-your-openai-api-key-here" ]; then \
		echo "ERROR: OPENAI_API_KEY not set in voice-parser/.env or still has placeholder value"; \
		exit 1; \
	fi; \
	aws secretsmanager create-secret \
		--region $(REGION) \
		--profile $(PROFILE) \
		--name "$(ENV)/openai/api-key" \
		--description "OpenAI API Key for $(ENV) environment" \
		--secret-string "$$OPENAI_API_KEY" \
		--tags Key=Environment,Value=$(ENV) Key=Service,Value=ai-voice-tool
	@echo "✓ OpenAI API Key secret created: $(ENV)/openai/api-key"

# Create all secrets
secrets-create: secrets-create-twilio-account-sid ssecrets-create-twilio-auth-token secrets-create-openai-api-key
	@echo "✓ All secrets created for environment: $(ENV)"

# Update Twilio Auth Token secret in AWS Secrets Manager
secrets-update-twilio-auth-token: secrets-check
	@echo "Updating Twilio Auth Token secret for environment: $(ENV)"
	@TWILIO_ACCOUNT_SID=$$(grep -E '^TWILIO_ACCOUNT_SID=' webhook-handler/.env | cut -d '=' -f2-); \
	if [ -z "$$TWILIO_ACCOUNT_SID" ] || [ "$$TWILIO_ACCOUNT_SID" = "your-twilio-account-sid-here" ]; then \
		echo "ERROR: TWILIO_ACCOUNT_SID not set in webhook-handler/.env or still has placeholder value"; \
		exit 1; \
	fi; \
	aws secretsmanager update-secret \
		--region $(REGION) \
		--profile $(PROFILE) \
		--secret-id "$(ENV)/twilio/account-sid" \
		--secret-string "$$TWILIO_ACCOUNT_SID"
	@echo "✓ Twilio Account SID secret updated: $(ENV)/twilio/account-sid"

# Update Twilio Auth Token secret in AWS Secrets Manager
secrets-update-twilio-auth-token: secrets-check
	@echo "Updating Twilio Auth Token secret for environment: $(ENV)"
	@TWILIO_AUTH_TOKEN=$$(grep -E '^TWILIO_AUTH_TOKEN=' webhook-handler/.env | cut -d '=' -f2-); \
	if [ -z "$$TWILIO_AUTH_TOKEN" ] || [ "$$TWILIO_AUTH_TOKEN" = "your-twilio-auth-token-here" ]; then \
		echo "ERROR: TWILIO_AUTH_TOKEN not set in webhook-handler/.env or still has placeholder value"; \
		exit 1; \
	fi; \
	aws secretsmanager update-secret \
		--region $(REGION) \
		--profile $(PROFILE) \
		--secret-id "$(ENV)/twilio/auth-token" \
		--secret-string "$$TWILIO_AUTH_TOKEN"
	@echo "✓ Twilio Auth Token secret updated: $(ENV)/twilio/auth-token"

# Update OpenAI API Key secret in AWS Secrets Manager
secrets-update-openai-api-key: secrets-check
	@echo "Updating OpenAI API Key secret for environment: $(ENV)"
	@OPENAI_API_KEY=$$(grep -E '^OPENAI_API_KEY=' voice-parser/.env | cut -d '=' -f2-); \
	if [ -z "$$OPENAI_API_KEY" ] || [ "$$OPENAI_API_KEY" = "sk-proj-your-openai-api-key-here" ]; then \
		echo "ERROR: OPENAI_API_KEY not set in voice-parser/.env or still has placeholder value"; \
		exit 1; \
	fi; \
	aws secretsmanager update-secret \
		--region $(REGION) \
		--profile $(PROFILE) \
		--secret-id "$(ENV)/openai/api-key" \
		--secret-string "$$OPENAI_API_KEY"
	@echo "✓ OpenAI API Key secret updated: $(ENV)/openai/api-key"

# Update all secrets
secrets-update: secrets-update-twilio-auth-token secrets-update-openai-api-key
	@echo "✓ All secrets updated for environment: $(ENV)"

# Get secret ARNs (useful for CloudFormation parameters)
secrets-get-arns:
	@echo "Secret ARNs for environment: $(ENV)"
	@echo ""
	@echo "TwilioAuthTokenSecretArn:"
	@aws secretsmanager describe-secret \
		--region $(REGION) \
		--profile $(PROFILE) \
		--secret-id "$(ENV)/twilio/auth-token" \
		--query 'ARN' \
		--output text 2>/dev/null || echo "  (not found - run 'make secrets-create' first)"
	@echo ""
	@echo "OpenAIApiKeySecretArn:"
	@aws secretsmanager describe-secret \
		--region $(REGION) \
		--profile $(PROFILE) \
		--secret-id "$(ENV)/openai/api-key" \
		--query 'ARN' \
		--output text 2>/dev/null || echo "  (not found - run 'make secrets-create' first)"

# --- Voice Parser ---
build-voice-parser:
	@echo "Building voice-parser for environment: $(ENV)"
	docker build --file voice-parser/Dockerfile -t $(VOICE_PARSER_IMG):$(TAG) .
	docker tag $(VOICE_PARSER_IMG):$(TAG) $(VOICE_PARSER_REPO):$(TAG)

push-voice-parser: ecr-login build-voice-parser
	@echo "Pushing voice-parser to $(VOICE_PARSER_REPO):$(TAG)"
	docker push $(VOICE_PARSER_REPO):$(TAG)
	@echo "✓ Voice parser image pushed successfully"

deploy-voice-parser: push-voice-parser
	@echo "Deploying voice-parser Lambda via CloudFormation..."
	./infrastructure/deploy.sh $(ENV) voice-parser
	@echo "✓ Voice parser deployed successfully"

# --- Webhook Handler ---
build-webhook-handler:
	@echo "Building webhook-handler for environment: $(ENV)"
	docker build --file webhook-handler/Dockerfile -t $(WEBHOOK_HANDLER_IMG):$(TAG) .
	docker tag $(WEBHOOK_HANDLER_IMG):$(TAG) $(WEBHOOK_HANDLER_REPO):$(TAG)

push-webhook-handler: ecr-login build-webhook-handler
	@echo "Pushing webhook-handler to $(WEBHOOK_HANDLER_REPO):$(TAG)"
	docker push $(WEBHOOK_HANDLER_REPO):$(TAG)
	@echo "✓ Webhook handler image pushed successfully"

deploy-webhook-handler: push-webhook-handler
	@echo "Deploying webhook-handler Lambda via CloudFormation..."
	./infrastructure/deploy.sh $(ENV) webhook-handler
	@echo "✓ Webhook handler deployed successfully"

# --- Customer Lookup ---
build-customer-lookup:
	@echo "Building customer-lookup for environment: $(ENV)"
	docker build --file customer-lookup-server/Dockerfile -t $(CUSTOMER_LOOKUP_IMG):$(TAG) .
	docker tag $(CUSTOMER_LOOKUP_IMG):$(TAG) $(CUSTOMER_LOOKUP_REPO):$(TAG)

push-customer-lookup: ecr-login build-customer-lookup
	@echo "Pushing customer-lookup to $(CUSTOMER_LOOKUP_REPO):$(TAG)"
	docker push $(CUSTOMER_LOOKUP_REPO):$(TAG)
	@echo "✓ Customer lookup image pushed successfully"

deploy-customer-lookup: push-customer-lookup
	@echo "Deploying customer-lookup Lambda via CloudFormation..."
	./infrastructure/deploy.sh $(ENV) customer-lookup
	@echo "✓ Customer lookup deployed successfully"

# --- Data API Server ---
build-data-api:
	@echo "Building data-api for environment: $(ENV)"
	docker build --file data-api-server/Dockerfile -t $(DATA_API_IMG):$(TAG) .
	docker tag $(DATA_API_IMG):$(TAG) $(DATA_API_REPO):$(TAG)

push-data-api: ecr-login build-data-api
	@echo "Pushing data-api to $(DATA_API_REPO):$(TAG)"
	docker push $(DATA_API_REPO):$(TAG)
	@echo "✓ Data API image pushed successfully"

deploy-data-api: push-data-api
	@echo "Deploying data-api Lambda via CloudFormation..."
	./infrastructure/deploy.sh $(ENV) data-api
	@echo "✓ Data API deployed successfully"

# --- Infrastructure Deployment (Non-Lambda) ---
deploy-ecr:
	@echo "Deploying ECR repositories via CloudFormation..."
	./infrastructure/deploy.sh $(ENV) ecr
	@echo "✓ ECR repositories deployed successfully"

deploy-shared:
	@echo "Deploying shared infrastructure (S3, SQS, API Gateway) via CloudFormation..."
	./infrastructure/deploy.sh $(ENV) shared
	@echo "✓ Shared infrastructure deployed successfully"

