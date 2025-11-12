# Webhook Handler Service

This service is an AWS Lambda function responsible for handling incoming webhook notifications from Twilio for WhatsApp messages. It acts as the primary entry point for all messages sent to the system's WhatsApp number.

## Core Responsibilities

1.  **Request Validation**: It authenticates incoming requests to ensure they originate from Twilio. This is done by validating the `X-Twilio-Signature` header using the `TWILIO_AUTH_TOKEN`.
2.  **Sender Authorization**: It checks if the sender's phone number (`From` field) is associated with a known and active customer. This is performed by calling the `customer-lookup-server`.
3.  **Payload Validation**: It ensures the incoming data structure conforms to the expected `TwilioWebhookPayload` model.
4.  **Queueing for Processing**: Upon successful validation and authorization, the service forwards the webhook payload to an AWS SQS queue for asynchronous processing by the `voice-parser` service.

## Workflow

```
Twilio (WhatsApp Message) -> AWS API Gateway -> Webhook Handler Lambda -> AWS SQS -> Voice Parser
```

## Error Handling

The service returns specific HTTP status codes in case of failures:

-   `400 Bad Request`: If the request body is missing or the payload structure is invalid.
-   `401 Unauthorized`: If the `X-Twilio-Signature` is missing or the sender's phone number is not authorized.
-   `403 Forbidden`: If the Twilio signature validation fails.
-   `500 Internal Server Error`: For configuration issues (e.g., missing environment variables) or failures in communicating with downstream services like SQS.

## Configuration

The service requires the following environment variables to be set:

-   `TWILIO_AUTH_TOKEN`: The authentication token from the Twilio account to validate webhook signatures.
-   `SQS_QUEUE_URL`: The URL of the AWS SQS queue where validated messages are sent.
-   The endpoint for the Customer Lookup service is resolved by the `CustomerLookupClient` in the `shared-lib`.

## Dependency management & shared library

- Local work uses `uv sync`, which installs `ai-voice-shared` from `../shared-lib` in editable mode via the `[tool.uv.sources]` configuration in `pyproject.toml`.
- Docker/CI builds use `requirements.deploy.txt`, where the first line is `ai-voice-shared @ file:///var/task/shared-lib`. The Dockerfile copies `shared-lib/` into `/var/task/shared-lib` before running `pip install -r requirements.deploy.txt`.
- To refresh pins run `make requirements-sync-webhook-handler` (or `make requirements-sync`) from the repo root; it rebuilds both requirement files and rewrites the shared-lib entry automatically.
- Keep `uv.lock` committed for local reproducibility; the `.deploy` file plus the vendored shared library control container determinism.
