# Customer Lookup Lambda Function

AWS Lambda function for looking up customer metadata by phone number.

## Overview

This Lambda function provides customer lookup functionality for the ai-voice-tool system. It receives a phone number and returns associated customer metadata including customer ID, company ID, and company name.

## Current Implementation

Currently uses hardcoded dummy data for testing. Will be extended to query a database in future iterations.

## API

### Input Event
```json
{
  "phone_number": "+61400000000"
}
```

### Success Response (200)
```json
{
  "statusCode": 200,
  "body": "{\"customer_id\": \"cust_dummy_001\", \"company_id\": \"comp_dummy_001\", \"company_name\": \"Dummy Test Company\"}"
}
```

### Not Found Response (404)
```json
{
  "statusCode": 404,
  "body": "{\"error\": \"Customer not found for phone: +61400000000\"}"
}
```

### Error Response (500)
```json
{
  "statusCode": 500,
  "body": "{\"error\": \"Internal server error\"}"
}
```

## Deployment

Build and deploy using the Makefile:

```bash
# Build Docker image
make build-customer-lookup

# Deploy to AWS Lambda
make deploy-customer-lookup
```

## Testing Locally

You can test the Lambda function locally using AWS SAM CLI or by invoking it directly after deployment:

```bash
aws lambda invoke \
  --function-name ai-voice-tool-customer-lookup \
  --payload '{"phone_number": "+61400000000"}' \
  --region ap-southeast-2 \
  --profile cohesv \
  response.json

cat response.json
```

## Dummy Data

The function currently has one hardcoded test customer:
- **Phone**: +61400000000
- **Customer ID**: cust_dummy_001
- **Company ID**: comp_dummy_001
- **Company Name**: Dummy Test Company

## Future Enhancements

- Database integration for dynamic customer lookup
- Caching layer for improved performance
- Additional lookup methods (by customer ID, email, etc.)
