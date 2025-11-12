FROM public.ecr.aws/lambda/python:3.13

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy shared library; runtime requirements reference this path
COPY shared-lib/ ./shared-lib/

# Copy deployment requirements
COPY voice-parser/requirements.deploy.txt ./requirements.deploy.txt

# Install dependencies using pip
RUN pip install --no-cache-dir -r requirements.deploy.txt

# Copy source code
COPY voice-parser/voice_parser/ ./voice_parser/

# Install the package
COPY voice-parser/pyproject.toml README.md ./
RUN pip install --no-deps .

# Set the Lambda handler
CMD ["voice_parser.handler.lambda_handler"]
