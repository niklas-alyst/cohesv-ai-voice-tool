# Customer Lookup Service

This service is an AWS Lambda function that provides an internal API for looking up customer metadata based on a phone number.

## Overview

This function is a core component for authorization and data routing. Other services, like the `webhook-handler`, invoke this function to verify that an incoming phone number belongs to a known customer before processing a request. It also provides essential metadata, such as `company_id`, used by downstream services to correctly partition data.

## Data Source

The customer data is sourced from a JSON file located in an S3 bucket.

-   **S3 Bucket**: `cohesv-ai-voice-tool`
-   **S3 Key**: `customers.json`

The service downloads and caches this file in memory for the lifetime of the Lambda execution environment to ensure low-latency lookups.

### Data Format

The `customers.json` file must be an array of JSON objects, where each object represents a customer and contains at least the following fields:

```json
[
  {
    "customer_id": "cust_123",
    "company_id": "comp_abc",
    "company_name": "Acme Corporation",
    "phone_number": "+14155552671"
  },
  {
    "customer_id": "cust_456",
    "company_id": "comp_xyz",
    "company_name": "Stark Industries",
    "phone_number": "+15105552671"
  }
]
```

## API

The function is invoked with a JSON payload containing the phone number.

### Input Payload

```json
{
  "phone_number": "+14155552671"
}
```

*Note: The `whatsapp:` prefix, if present, is automatically removed by the handler.*

### Success Response (200 OK)

If a customer is found, the function returns a `200` status code with the customer's core metadata.

```json
{
  "statusCode": 200,
  "body": "{\"customer_id\": \"cust_123\", \"company_id\": \"comp_abc\", \"company_name\": \"Acme Corporation\"}"
}
```

### Not Found Response (404 Not Found)

If no customer matches the phone number, the function returns a `404` status code.

```json
{
  "statusCode": 404,
  "body": "{\"error\": \"Customer not found for phone: +14155552671\"}"
}
```

### Error Responses

-   **400 Bad Request**: Returned if the `phone_number` parameter is missing from the input payload.
-   **500 Internal Server Error**: Returned for any other unexpected errors, such as a failure to load the data from S3.

## Deployment & Testing

Deployment is handled via the project's root `Makefile`.

To test the deployed Lambda function directly from your CLI:

```bash
aws lambda invoke \
  --function-name ai-voice-tool-customer-lookup \
  --payload '{"phone_number": "+14155552671"}' \
  response.json

cat response.json
```