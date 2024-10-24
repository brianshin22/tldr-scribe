from flask import Flask, send_from_directory
import os
from dotenv import load_dotenv
from bot import TLDRBot
import threading

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configuration
DEFAULT_HOST = "http://localhost:5000"
TRANSCRIPT_DIR = 'transcripts'

# Ensure transcripts directory exists
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)

# Set BASE_URL environment variable if not set
if "BASE_URL" not in os.environ:
    os.environ["BASE_URL"] = DEFAULT_HOST
    print(f"No BASE_URL found in environment, using default: {DEFAULT_HOST}")

# Route for serving transcripts
@app.route('/transcript/<filename>')
def serve_transcript(filename):
    return send_from_directory(TRANSCRIPT_DIR, filename)

def start_bot():
    bot = TLDRBot()
    bot.start()

if __name__ == "__main__":
    # Start the bot in a separate thread
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    
    # Start the Flask server
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)