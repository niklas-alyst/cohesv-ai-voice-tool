FROM public.ecr.aws/lambda/python:3.13

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy shared library and deployment requirements
COPY shared-lib/ ./shared-lib/
COPY data-api-server/requirements.deploy.txt ./requirements.deploy.txt

# Install dependencies using pip
RUN pip install --no-cache-dir -r requirements.deploy.txt

# Copy source code
COPY data-api-server/src/data_api_server/ ./data_api_server/

# Install the package
COPY data-api-server/pyproject.toml data-api-server/README.md ./
RUN pip install --no-deps .

# Set the Lambda handler
CMD ["data_api_server.main.handler"]
