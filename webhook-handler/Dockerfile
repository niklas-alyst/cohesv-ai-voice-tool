FROM public.ecr.aws/lambda/python:3.13

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy requirements file
COPY put-message-in-queue/requirements.txt ./

# Install dependencies using pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY put-message-in-queue/webhook_handler/ ./webhook_handler/

# Install the package
COPY put-message-in-queue/pyproject.toml README.md ./
RUN pip install --no-deps .

# Set the Lambda handler
CMD ["webhook_handler.handler.lambda_handler"]
