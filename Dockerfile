FROM public.ecr.aws/lambda/python:3.13

# Copy requirements.txt
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install the specified packages
RUN pip install -r requirements.txt

# Copy source code
COPY src/ ${LAMBDA_TASK_ROOT}

# Install the package in editable mode
RUN pip install -e .