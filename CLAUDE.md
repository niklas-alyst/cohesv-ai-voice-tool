# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This document details the technical architecture for the WhatsApp AI Assistant, built on Python and deployed on Amazon Web Services (AWS). The design follows a two-phase evolution. Phase 1 prioritizes rapid deployment with a single, unified service. Phase 2 transitions the system to a decoupled, queue-based architecture to enhance resilience and scalability. The core of the system is a worker service that contains all the business logic for processing voice notes.

## **Worker service - Python FastAPI application**

The core of the system is a Python application built with the FastAPI framework. This service contains all the business logic required to process a voice note, including orchestrating calls to external transcription (Whisper) and structuring (LLM) APIs.

### **Data flow**

This flow details the worker's process once a job has been placed on the message queue in the Phase 2 architecture.

Code snippet

`sequenceDiagram
    participant Worker Service (ECS)
    participant AWS SQS
    participant AWS S3
    participant WhatsApp API
    participant Whisper API
    participant LLM API
    participant Database

    Worker Service (ECS)->>AWS SQS: Polls and receives job message
    Worker Service (ECS)->>WhatsApp API: Gets temporary media URL from message
    Worker Service (ECS)->>WhatsApp API: Downloads .ogg audio file
    Worker Service (ECS)->>AWS S3: Uploads audio file for persistent storage
    Worker Service (ECS)->>Whisper API: Sends audio file for transcription
    Whisper API-->>Worker Service (ECS): Returns raw text
    Worker Service (ECS)->>LLM API: Sends text with structuring prompt
    LLM API-->>Worker Service (ECS): Returns structured JSON
    Worker Service (ECS)->>Database: Saves final JSON output
    Worker Service (ECS)->>AWS SQS: Deletes job message from queue`

### **Deployment**

The Python FastAPI application will be containerized using a `Dockerfile`. This container will be deployed to **AWS Elastic Container Service (ECS)** using the **Fargate** launch type. Fargate allows us to run containers without managing servers or clusters.

The ECS service will be configured to automatically scale the number of running worker tasks based on the number of messages visible in the SQS queue. This ensures that we can handle traffic spikes cost-effectively.

## **Storage - AWS S3**

An **Amazon S3 bucket** will be used for the persistent storage of all incoming audio files. As soon as the worker service downloads an audio file from WhatsApp's temporary URL, it will be immediately uploaded to our S3 bucket. This guarantees that the original data is never lost, even if a downstream step in the AI processing pipeline fails. The worker can then safely retry processing using the file stored in S3.

## **Phase 1: WhatsApp webhook, part of worker service**

In the initial phase, the system is deployed as a single, monolithic service. The WhatsApp webhook endpoint is exposed directly by the main FastAPI application, which also contains the AI processing logic.

### **Data flow**

The process is synchronous and handled within a single API request.

Code snippet

`sequenceDiagram
    participant WhatsApp
    participant FastAPI Service (on ECS)
    participant Whisper API
    participant LLM API

    WhatsApp->>FastAPI Service (on ECS): POST /webhook/whatsapp
    activate FastAPI Service (on ECS)
    FastAPI Service (on ECS)->>WhatsApp: Downloads audio directly
    FastAPI Service (on ECS)->>Whisper API: Transcribes audio
    Whisper API-->>FastAPI Service (on ECS): Returns raw text
    FastAPI Service (on ECS)->>LLM API: Structures text
    LLM API-->>FastAPI Service (on ECS): Returns structured JSON
    Note over FastAPI Service (on ECS): Saves result to database
    FastAPI Service (on ECS)-->>WhatsApp: 200 OK
    deactivate FastAPI Service (on ECS)`

## **Phase 2: WhatsApp webhook, AWS SQS**

In this phase, the system is decoupled to improve resilience. The webhook ingestion is separated from the AI processing using an **Amazon Simple Queue Service (SQS)** queue. A lightweight service is introduced solely to handle webhook ingestion.

### **Data flow**

The process becomes asynchronous, separating the initial, fast response from the subsequent, slow processing.

Code snippet

`sequenceDiagram
    participant WhatsApp
    participant API Gateway
    participant Lambda Function
    participant AWS SQS
    participant Worker Service (ECS)

    WhatsApp->>API Gateway: POST /webhook/whatsapp
    API Gateway->>Lambda Function: Invokes function with payload
    activate Lambda Function
    Lambda Function->>AWS SQS: Enqueues webhook JSON payload
    Lambda Function-->>API Gateway: Returns 200 OK
    API Gateway-->>WhatsApp: 200 OK (Instant Response)
    deactivate Lambda Function

    Note right of AWS SQS: Message waits in queue...

    Worker Service (ECS)->>AWS SQS: Polls and receives message
    Note over Worker Service (ECS): Begins long-running process (download, AI calls, etc.)`
