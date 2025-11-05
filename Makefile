# Variables
ECR_REGISTRY := 404293832854.dkr.ecr.ap-southeast-2.amazonaws.com
REGION := ap-southeast-2
PROFILE := cohesv
TAG := latest

# Service Repositories
VOICE_PARSER_REPO := $(ECR_REGISTRY)/ai-voice-tool/voice-parser
WEBHOOK_HANDLER_REPO := $(ECR_REGISTRY)/ai-voice-tool/webhook-handler

# Image Names
VOICE_PARSER_IMG := voice-parser
WEBHOOK_HANDLER_IMG := webhook-handler

# Lambda Function Names
VOICE_PARSER_LAMBDA := ai-voice-tool-voice-parser
WEBHOOK_HANDLER_LAMBDA := ai-voice-tool-webhook-handler

.PHONY: all build deploy build-voice-parser deploy-voice-parser build-webhook-handler deploy-webhook-handler update-voice-parser-lambda update-webhook-handler-lambda update-lambdas install-shared-lib install-shared-lib-voice-parser install-shared-lib-webhook-handler

all: build
build: build-voice-parser build-webhook-handler
deploy: deploy-voice-parser deploy-webhook-handler

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

# --- Update all Lambda functions ---
update-lambdas: update-voice-parser-lambda update-webhook-handler-lambda