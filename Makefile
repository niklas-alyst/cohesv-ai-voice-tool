# Variables
REGISTRY := 404293832854.dkr.ecr.ap-southeast-2.amazonaws.com/ai-voice-tool
REGION := ap-southeast-2
PROFILE := cohesv
IMAGE_NAME := voice-parser
TAG := latest

.PHONY: build deploy

build:
	docker build -t $(IMAGE_NAME):$(TAG) .
	docker tag $(IMAGE_NAME):$(TAG) $(REGISTRY):$(TAG)

deploy: build
	aws ecr get-login-password --region $(REGION) --profile $(PROFILE) | docker login --username AWS --password-stdin $(REGISTRY)
	docker push $(REGISTRY):$(TAG)
