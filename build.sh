#!/bin/bash

# Specify the project directory path
PROJECT_PATH="."

# Specify the project directory name
PROJECT_DIR="pickem-api"

# Specify the target directory where dependencies will be installed
TARGET_DIR="/package"

# Step 1: Run a Docker container based on Amazon Linux in detached mode
CONTAINER_ID=$(docker run -d amazonlinux:latest tail -f /dev/null)

# Step 2: Install the necessary tools and dependencies inside the Docker container
docker exec $CONTAINER_ID yum update -y
docker exec $CONTAINER_ID yum install -y python3.11 python3.11-devel python3.11-pip zip
docker exec $CONTAINER_ID pip3.11 install poetry

# Step 3: Activate the virtual environment with Python 3.11
docker exec $CONTAINER_ID poetry env use python3.11

# Step 4: Copy your project code into the Docker container
docker cp $PROJECT_PATH/. $CONTAINER_ID:/$PROJECT_DIR

# Step 5: Build and package your Python project
docker exec $CONTAINER_ID bash -c "cd /$PROJECT_DIR && poetry install && poetry build"
docker exec $CONTAINER_ID mkdir /$PROJECT_DIR/deployment-package

# Step 6: Install project dependencies into the target directory
docker exec $CONTAINER_ID bash -c "cd /$PROJECT_DIR && poetry run pip install --upgrade -t $TARGET_DIR dist/*.whl"
docker exec $CONTAINER_ID bash -c "ls -ltr $TARGET_DIR"

# Step 7: Copy the installed dependencies into the deployment package directory
docker exec $CONTAINER_ID bash -c "cp -r $TARGET_DIR/* /$PROJECT_DIR/deployment-package/"

# Step 8: Zip the deployment package
docker exec $CONTAINER_ID bash -c "cd /$PROJECT_DIR/deployment-package && zip -r9 lambda-deployment-package.zip ."

# Copy the zip file back to your host
docker cp $CONTAINER_ID:/$PROJECT_DIR/deployment-package/lambda-deployment-package.zip $PROJECT_PATH

# Step 9: Stop and remove the Docker container
docker stop $CONTAINER_ID
docker rm $CONTAINER_ID
