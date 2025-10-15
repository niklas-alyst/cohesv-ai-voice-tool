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

.PHONY: all build deploy build-voice-parser deploy-voice-parser build-webhook-handler deploy-webhook-handler

all: build
build: build-voice-parser build-webhook-handler
deploy: deploy-voice-parser deploy-webhook-handler

# --- Voice Parser ---
build-voice-parser:
	docker build --file parse-message/Dockerfile -t $(VOICE_PARSER_IMG):$(TAG) .
	docker tag $(VOICE_PARSER_IMG):$(TAG) $(VOICE_PARSER_REPO):$(TAG)

deploy-voice-parser: build-voice-parser
	aws ecr get-login-password --region $(REGION) --profile $(PROFILE) | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	docker push $(VOICE_PARSER_REPO):$(TAG)

# --- Webhook Handler ---
build-webhook-handler:
	docker build --file put-message-in-queue/Dockerfile -t $(WEBHOOK_HANDLER_IMG):$(TAG) .
	docker tag $(WEBHOOK_HANDLER_IMG):$(TAG) $(WEBHOOK_HANDLER_REPO):$(TAG)

deploy-webhook-handler: build-webhook-handler
	aws ecr get-login-password --region $(REGION) --profile $(PROFILE) | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	docker push $(WEBHOOK_HANDLER_REPO):$(TAG)