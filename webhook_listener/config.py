import os

# Path to your Git repository on the VM
# Replace this with the absolute path to your repository
REPO_PATH = '/home/user_ccp/service'

# Secret token for webhook verification
# Replace this with your actual secret token
SECRET_TOKEN = 'c52593014806b68d14a33f7c45ae7c644cd4601040d081a806206611f8111e02'

# The port on which the webhook listener will run
PORT = 5000

# Whether to run the app in debug mode (False for production)
DEBUG = False 