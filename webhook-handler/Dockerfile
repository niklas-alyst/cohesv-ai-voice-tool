FROM public.ecr.aws/lambda/python:3.13

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy shared library and deployment requirements
COPY shared-lib/ ./shared-lib/
COPY webhook-handler/requirements.deploy.txt ./requirements.deploy.txt

# Install dependencies using pip
RUN pip install --no-cache-dir -r requirements.deploy.txt

# Copy source code
COPY webhook-handler/webhook_handler/ ./webhook_handler/

# Install the package
COPY webhook-handler/pyproject.toml README.md ./
RUN pip install --no-deps .

# Set the Lambda handler
CMD ["webhook_handler.handler.lambda_handler"]
