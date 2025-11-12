# Dockerfile for Data API Authorizer Lambda
FROM public.ecr.aws/lambda/python:3.13

# Copy the authorizer function
COPY data-api-authorizer/authorizer.py ${LAMBDA_TASK_ROOT}/

# Install boto3 (already included in Lambda runtime, but explicit for clarity)
RUN pip install --no-cache-dir boto3

# Set the CMD to the handler
CMD ["authorizer.lambda_handler"]
