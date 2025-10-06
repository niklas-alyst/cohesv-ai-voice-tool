FROM public.ecr.aws/lambda/python:3.13

# Install uv for dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
RUN uv pip install --system -r pyproject.toml

# Copy source code
COPY src/ ./

# Install the package
RUN uv pip install --system --no-deps .

# Set the Lambda handler
CMD ["voice_parser.worker_handler.lambda_handler"]