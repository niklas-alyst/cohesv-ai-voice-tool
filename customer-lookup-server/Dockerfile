FROM public.ecr.aws/lambda/python:3.13

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy requirements file
COPY customer-lookup-server/requirements.txt ./

# Install dependencies using pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY customer-lookup-server/customer_lookup_server/ ./customer_lookup_server/

# Install the package
COPY customer-lookup-server/pyproject.toml customer-lookup-server/README.md ./
RUN pip install --no-deps .

# Set the Lambda handler
CMD ["customer_lookup_server.handler.lambda_handler"]
