# Variables
ECR_REGISTRY := 404293832854.dkr.ecr.ap-southeast-2.amazonaws.com
REGION := ap-southeast-2
PROFILE := cohesv
TAG := latest

# Service Repositories
VOICE_PARSER_REPO := $(ECR_REGISTRY)/ai-voice-tool/voice-parser
WEBHOOK_HANDLER_REPO := $(ECR_REGISTRY)/ai-voice-tool/webhook-handler
CUSTOMER_LOOKUP_REPO := $(ECR_REGISTRY)/ai-voice-tool/customer-lookup-server
DATA_API_REPO := $(ECR_REGISTRY)/ai-voice-tool/data-api-server

# Image Names
VOICE_PARSER_IMG := voice-parser
WEBHOOK_HANDLER_IMG := webhook-handler
CUSTOMER_LOOKUP_IMG := customer-lookup-server
DATA_API_IMG := data-api-server

# Lambda Function Names
VOICE_PARSER_LAMBDA := ai-voice-tool-voice-parser
WEBHOOK_HANDLER_LAMBDA := ai-voice-tool-webhook-handler
CUSTOMER_LOOKUP_LAMBDA := ai-voice-tool-customer-lookup-server
DATA_API_LAMBDA := ai-voice-tool-data-api-server

.PHONY: all build deploy build-voice-parser deploy-voice-parser build-webhook-handler deploy-webhook-handler build-customer-lookup deploy-customer-lookup build-data-api deploy-data-api update-voice-parser-lambda update-webhook-handler-lambda update-customer-lookup-lambda update-data-api-lambda update-lambdas install-shared-lib install-shared-lib-voice-parser install-shared-lib-webhook-handler

all: build
build: build-voice-parser build-webhook-handler build-customer-lookup build-data-api
deploy: deploy-voice-parser deploy-webhook-handler deploy-customer-lookup deploy-data-api

# --- Shared Library (Local Development) ---
install-shared-lib-voice-parser:
	cd voice-parser && uv add --editable ../shared-lib

install-shared-lib-webhook-handler:
	cd webhook-handler && uv add --editable ../shared-lib

install-shared-lib: install-shared-lib-voice-parser install-shared-lib-webhook-handler

# --- Voice Parser ---
build-voice-parser:
	docker build --file voice-parser/Dockerfile -t $(VOICE_PARSER_IMG):$(TAG) .
	docker tag $(VOICE_PARSER_IMG):$(TAG) $(VOICE_PARSER_REPO):$(TAG)

deploy-voice-parser: build-voice-parser
	aws ecr get-login-password --region $(REGION) --profile $(PROFILE) | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	docker push $(VOICE_PARSER_REPO):$(TAG)
	$(MAKE) update-voice-parser-lambda

update-voice-parser-lambda:
	@echo "Updating Lambda function $(VOICE_PARSER_LAMBDA) with new image..."
	aws lambda update-function-code \
		--function-name $(VOICE_PARSER_LAMBDA) \
		--image-uri $(VOICE_PARSER_REPO):$(TAG) \
		--region $(REGION) \
		--profile $(PROFILE)
	@echo "Waiting for Lambda function to be updated..."
	aws lambda wait function-updated \
		--function-name $(VOICE_PARSER_LAMBDA) \
		--region $(REGION) \
		--profile $(PROFILE)
	@echo "Lambda function $(VOICE_PARSER_LAMBDA) updated successfully!"

# --- Webhook Handler ---
build-webhook-handler:
	docker build --file webhook-handler/Dockerfile -t $(WEBHOOK_HANDLER_IMG):$(TAG) .
	docker tag $(WEBHOOK_HANDLER_IMG):$(TAG) $(WEBHOOK_HANDLER_REPO):$(TAG)

deploy-webhook-handler: build-webhook-handler
	aws ecr get-login-password --region $(REGION) --profile $(PROFILE) | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	docker push $(WEBHOOK_HANDLER_REPO):$(TAG)
	$(MAKE) update-webhook-handler-lambda

update-webhook-handler-lambda:
	@echo "Updating Lambda function $(WEBHOOK_HANDLER_LAMBDA) with new image..."
	aws lambda update-function-code \
		--function-name $(WEBHOOK_HANDLER_LAMBDA) \
		--image-uri $(WEBHOOK_HANDLER_REPO):$(TAG) \
		--region $(REGION) \
		--profile $(PROFILE)
	@echo "Waiting for Lambda function to be updated..."
	aws lambda wait function-updated \
		--function-name $(WEBHOOK_HANDLER_LAMBDA) \
		--region $(REGION) \
		--profile $(PROFILE)
	@echo "Lambda function $(WEBHOOK_HANDLER_LAMBDA) updated successfully!"

# --- Customer Lookup ---
build-customer-lookup:
	docker build --file customer-lookup-server/Dockerfile -t $(CUSTOMER_LOOKUP_IMG):$(TAG) .
	docker tag $(CUSTOMER_LOOKUP_IMG):$(TAG) $(CUSTOMER_LOOKUP_REPO):$(TAG)

deploy-customer-lookup: build-customer-lookup
	aws ecr get-login-password --region $(REGION) --profile $(PROFILE) | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	docker push $(CUSTOMER_LOOKUP_REPO):$(TAG)
	$(MAKE) update-customer-lookup-lambda

update-customer-lookup-lambda:
	@echo "Updating Lambda function $(CUSTOMER_LOOKUP_LAMBDA) with new image..."
	aws lambda update-function-code \
		--function-name $(CUSTOMER_LOOKUP_LAMBDA) \
		--image-uri $(CUSTOMER_LOOKUP_REPO):$(TAG) \
		--region $(REGION) \
		--profile $(PROFILE)
	@echo "Waiting for Lambda function to be updated..."
	aws lambda wait function-updated \
		--function-name $(CUSTOMER_LOOKUP_LAMBDA) \
		--region $(REGION) \
		--profile $(PROFILE)
	@echo "Lambda function $(CUSTOMER_LOOKUP_LAMBDA) updated successfully!"

# --- Data API Server ---
build-data-api:
	docker build --file data-api-server/Dockerfile -t $(DATA_API_IMG):$(TAG) .
	docker tag $(DATA_API_IMG):$(TAG) $(DATA_API_REPO):$(TAG)

deploy-data-api: build-data-api
	aws ecr get-login-password --region $(REGION) --profile $(PROFILE) | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	docker push $(DATA_API_REPO):$(TAG)
	$(MAKE) update-data-api-lambda

update-data-api-lambda:
	@echo "Updating Lambda function $(DATA_API_LAMBDA) with new image..."
	aws lambda update-function-code \
		--function-name $(DATA_API_LAMBDA) \
		--image-uri $(DATA_API_REPO):$(TAG) \
		--region $(REGION) \
		--profile $(PROFILE)
	@echo "Waiting for Lambda function to be updated..."
	aws lambda wait function-updated \
		--function-name $(DATA_API_LAMBDA) \
		--region $(REGION) \
		--profile $(PROFILE)
	@echo "Lambda function $(DATA_API_LAMBDA) updated successfully!"

# --- Update all Lambda functions ---
update-lambdas: update-voice-parser-lambda update-webhook-handler-lambda update-customer-lookup-lambda update-data-api-lambda