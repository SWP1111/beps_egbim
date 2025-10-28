import os
import hmac
import hashlib
import subprocess
import logging
from flask import Flask, request, jsonify
from config import REPO_PATH, SECRET_TOKEN, PORT, DEBUG

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("webhook.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def verify_signature(payload, signature):
    """Verify that the webhook payload was sent from GitHub by validating the signature"""
    if not signature:
        return False
    
    # The signature from GitHub is in the format "sha256=SIGNATURE"
    sha_name, signature = signature.split('=', 1)
    if sha_name != 'sha256':
        return False

    # Create our own signature for comparison
    mac = hmac.new(SECRET_TOKEN.encode(), msg=payload, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)

def pull_latest_changes():
    """Pull the latest changes from the Git repository"""
    try:
        logger.info("Pulling latest changes from repository...")
        result = subprocess.run(
            ['git', 'pull'],
            cwd=REPO_PATH,
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"Git pull result: {result.stdout}")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to pull changes: {e.stderr}")
        return False, e.stderr

@app.route('/webhook', methods=['POST'])
def webhook():
    # Get the X-Hub-Signature-256 header
    signature = request.headers.get('X-Hub-Signature-256')
    
    # Get the raw JSON payload
    payload = request.data
    
    # Verify the signature
    if not verify_signature(payload, signature):
        logger.warning("Invalid signature - Unauthorized webhook request")
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    # Get the JSON data
    data = request.json
    
    # Check if it's a push event
    if request.headers.get('X-GitHub-Event') == 'push':
        logger.info(f"Received push event from {data.get('repository', {}).get('full_name')}")
        
        # Pull the latest changes
        success, message = pull_latest_changes()
        
        if success:
            return jsonify({"status": "success", "message": "Changes pulled successfully"}), 200
        else:
            return jsonify({"status": "error", "message": message}), 500
    
    # For other events, just acknowledge
    return jsonify({"status": "ignored", "message": "Event ignored"}), 200

if __name__ == '__main__':
    # Run the Flask app using settings from config
    app.run(host='0.0.0.0', port=PORT, debug=DEBUG) 