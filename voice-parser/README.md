# Voice Parser Service

This service is an AWS Lambda function that acts as an asynchronous worker, triggered by messages placed in an SQS queue. Its primary role is to receive validated WhatsApp message payloads from the `webhook-handler`, process them by extracting meaningful information, and persist the results.

## Core Responsibilities

1.  **Message Consumption**: Ingests `TwilioWebhookPayload` messages from an AWS SQS queue.
2.  **Content Processing**: Handles both `text` and `audio` messages.
    -   For **audio messages**, it downloads the media file from Twilio's content URL.
    -   The audio is then transcribed into text using a transcription service (e.g., OpenAI Whisper).
3.  **Intelligent Structuring**: The resulting text (either from transcription or the original text message) is analyzed by a Large Language Model (LLM).
    -   The LLM first determines the **intent** of the message (e.g., `JOB_TO_BE_DONE`, `KNOWLEDGE_DOCUMENT`, `OTHER`).
    -   If the intent is actionable, the LLM performs a detailed analysis to structure the content into a predefined format.
4.  **Customer-Specific Data Handling**: It fetches customer metadata from the `customer-lookup-server` to associate the processed data with the correct company and to use the `company_id` in the storage path.
5.  **Artifact Persistence**: All generated artifacts are uploaded to an S3 bucket for long-term storage and analysis. This includes:
    -   The original audio file (if applicable).
    -   The full, transcribed text.
    -   The final, structured analysis text.
    The artifacts are stored under a prefix that includes the `company_id`, message intent, and a unique identifier.
6.  **User Feedback**: The service communicates its progress back to the original sender via WhatsApp.
    -   An initial "message received" confirmation is sent.
    -   Once processing is complete, the structured analysis (or a simple confirmation for `OTHER` intents) is sent to the user.

## Workflow

```
SQS -> Voice Parser Lambda -> (Customer Lookup)
                          -> (Twilio API for media download)
                          -> (Transcription Service)
                          -> (LLM Service for analysis)
                          -> (S3 for artifact storage)
                          -> (Twilio API for user feedback)
```

## Error Handling

The Lambda function is configured to handle partial batch failures. If processing for a single SQS message fails, its `itemIdentifier` is returned to SQS, allowing the message to be automatically retried without affecting the rest of the batch.

## Dependencies

-   **AWS SQS**: For receiving message payloads.
-   **AWS S3**: For storing all artifacts.
-   **Customer Lookup Service**: To retrieve customer metadata.
-   **Twilio API**: To download media and send messages.
-   **Transcription Service**: An external service for audio-to-text conversion.
-   **LLM Service**: An external service for text analysis and structuring.

## Local development vs. deployment dependencies

- **Local**: Run `uv sync` inside `voice-parser/`. The `[tool.uv.sources]` block keeps `ai-voice-shared` (../shared-lib) installed in editable mode so changes propagate immediately.
- **Docker/CI**: The container build sticks to `pip install -r requirements.deploy.txt`. That file is a pinned copy of `requirements.txt`, except the editable line is replaced with `ai-voice-shared @ file:///var/task/shared-lib`. The Dockerfile copies `shared-lib/` into `/var/task/shared-lib` before installing dependencies so the file URL resolves.
- **Updating pins**: run `make requirements-sync-voice-parser` (or the top-level `make requirements-sync`) from the repo root. The Make target runs `uv pip compile`, copies the file, and rewrites the shared-lib line automatically.
- Keep `uv.lock` checked in so local environments stay reproducible, while Docker images rely solely on the `.deploy` requirements file plus the vendored shared library.
