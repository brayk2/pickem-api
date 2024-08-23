import base64
import os


def _generate_key():
    key = os.urandom(32)
    base64_key = base64.urlsafe_b64encode(key).decode()
    return base64_key


"""

# Use this code snippet in your app.
# If you need more information about configurations
# or implementing the sample code, visit the AWS docs:
# https://aws.amazon.com/developer/language/python/

import boto3
from botocore.exceptions import ClientError





"""
