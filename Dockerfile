FROM public.ecr.aws/lambda/python:3.11

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
ENV LANGUAGE=C.UTF-8

# Install poetry
RUN pip install poetry

# Copy only requirements to cache them in docker layer
WORKDIR ${LAMBDA_TASK_ROOT}
COPY poetry.lock pyproject.toml ${LAMBDA_TASK_ROOT}/

# Project initialization:
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi --no-root

# Copy our Flask src to the Docker image
COPY src ${LAMBDA_TASK_ROOT}/src

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD [ "src.app.handler" ]