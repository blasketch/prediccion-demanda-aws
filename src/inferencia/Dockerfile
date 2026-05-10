FROM public.ecr.aws/lambda/python:3.12

# System dependency required by xgboost (OpenMP runtime)
RUN dnf install -y libgomp && dnf clean all

# Install Python dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install --no-cache-dir -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Copy function code
COPY lambda_function.py ${LAMBDA_TASK_ROOT}

# Set the handler
CMD [ "lambda_function.lambda_handler" ]
