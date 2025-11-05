FROM public.ecr.aws/lambda/python:3.13

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy and install shared library first
COPY shared-lib/ ./shared-lib/
RUN pip install --no-cache-dir ./shared-lib

# Copy requirements file
COPY webhook-handler/requirements.txt ./

# Install dependencies using pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY webhook-handler/webhook_handler/ ./webhook_handler/

# Install the package
COPY webhook-handler/pyproject.toml README.md ./
RUN pip install --no-deps .

# Set the Lambda handler
CMD ["webhook_handler.handler.lambda_handler"]
