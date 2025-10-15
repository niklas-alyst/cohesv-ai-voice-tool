FROM public.ecr.aws/lambda/python:3.13

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy requirements file
COPY voice-parser/requirements.txt ./

# Install dependencies using pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY voice-parser/voice_parser/ ./voice_parser/

# Install the package
COPY voice-parser/pyproject.toml README.md ./
RUN pip install --no-deps .

# Set the Lambda handler
CMD ["voice_parser.worker_handler.lambda_handler"]