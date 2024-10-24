import tweepy
import os
import replicate
from pytube import YouTube
import json
import tempfile
import markdown
import hashlib
from datetime import datetime, timezone
import time

class TranscriptFormatter:
    """Handles the formatting and saving of transcripts as HTML files"""
    
    HTML_TEMPLATE = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                max-width: 800px;
                margin: 0 auto;
                padding: 2rem;
                background: #f5f5f5;
            }
            .container {
                background: white;
                padding: 2rem;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }
            .metadata {
                color: #666;
                font-size: 0.9rem;
                margin-bottom: 2rem;
                padding-bottom: 1rem;
                border-bottom: 1px solid #eee;
            }
            .content {
                font-size: 1.1rem;
            }
            h1 {
                color: #2c3e50;
                margin-top: 0;
            }
            .summary {
                background: #f8f9fa;
                padding: 1.5rem;
                border-left: 4px solid #4a9eff;
                margin: 1.5rem 0;
            }
            .transcript {
                margin-top: 2rem;
            }
            .timestamp {
                color: #666;
                font-size: 0.9rem;
                margin-right: 0.5rem;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>{title}</h1>
            <div class="metadata">
                <div>Transcribed: {date}</div>
                <div>Original Tweet: <a href="{tweet_url}">View on Twitter</a></div>
            </div>
            <div class="content">
                <div class="summary">
                    <h2>Summary</h2>
                    {summary}
                </div>
                <div class="transcript">
                    <h2>Full Transcript</h2>
                    {content}
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    def __init__(self, transcript_dir="transcripts"):
        self.transcript_dir = transcript_dir
        os.makedirs(transcript_dir, exist_ok=True)
    
    def format_transcript(self, transcript, summary, tweet_url):
        """Formats transcript and summary as HTML"""
        markdown_content = "\n\n".join(line.strip() for line in transcript.split("\n") if line.strip())
        summary_content = summary.replace("•", "*")
        
        html_content = markdown.markdown(markdown_content)
        html_summary = markdown.markdown(summary_content)
        
        transcript_id = hashlib.md5(transcript.encode()).hexdigest()[:10]
        
        html = self.HTML_TEMPLATE.format(
            title="Video Transcript",
            date=datetime.now().strftime("%B %d, %Y"),
            tweet_url=tweet_url,
            summary=html_summary,
            content=html_content
        )
        
        filename = f"transcript_{transcript_id}.html"
        filepath = os.path.join(self.transcript_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        
        return filename


class TLDRBot:
    def __init__(self):
        # Initialize Twitter API v2 client
        self.client = tweepy.Client(
            consumer_key=os.environ.get("TWITTER_API_KEY"),
            consumer_secret=os.environ.get("TWITTER_API_SECRET"),
            access_token=os.environ.get("TWITTER_ACCESS_TOKEN"),
            access_token_secret=os.environ.get("TWITTER_ACCESS_TOKEN_SECRET"),
            bearer_token=os.environ.get("TWITTER_BEARER_TOKEN"),
            wait_on_rate_limit=True
        )
        
        # Initialize Replicate client
        self.replicate_client = replicate.Client(api_token=os.environ.get("REPLICATE_API_TOKEN"))
        
        # Initialize transcript formatter
        self.transcript_formatter = TranscriptFormatter()
        
        # Store last processed mention ID instead of time
        self.last_mention_id = None
        
    def get_new_mentions(self):
        """Gets new mentions of the bot"""
        try:
            # Get mentions with expanded tweet info
            mentions = self.client.get_users_mentions(
                id=self.client.get_me().data.id,  # Get bot's own user ID
                max_results=5,  # Limit to 5 mentions per check
                since_id=self.last_mention_id,  # Only get mentions newer than last processed
                tweet_fields=['created_at', 'referenced_tweets'],
                expansions=['referenced_tweets.id']
            )
            
            if not mentions.data:
                return []
            
            # Update last mention ID
            self.last_mention_id = max(tweet.id for tweet in mentions.data)
            
            # Filter for replies only
            new_mentions = []
            for mention in mentions.data:
                if (hasattr(mention, 'referenced_tweets') and 
                    mention.referenced_tweets and 
                    any(ref.type == "replied_to" for ref in mention.referenced_tweets)):
                    new_mentions.append(mention)
            
            return new_mentions
            
        except Exception as e:
            print(f"Error getting mentions: {str(e)}")
            return []

    def get_video_url(self, tweet_id):
        """Gets video URL from tweet - NOTE: This needs manual implementation"""
        try:
            # Due to API limitations, you'll need to either:
            # 1. Have users reply with the video URL
            # 2. Have users use a specific format like "transcribe: [URL]"
            # 3. Use web scraping (not recommended)
            # This is a limitation of the Free API tier
            
            tweet = self.client.get_tweet(tweet_id, expansions=["attachments.media_keys"])
            if tweet.includes and 'media' in tweet.includes:
                # Note: Free tier doesn't provide direct video URLs
                # You'll need to handle this differently
                pass
            return None
        except Exception as e:
            print(f"Error getting video URL: {str(e)}")
            return None

    def run(self):
        """Main bot loop"""
        print("Bot started - checking for mentions...")
        
        # Get bot's own user ID on startup
        try:
            me = self.client.get_me()
            print(f"Bot running as user @{me.data.username}")
        except Exception as e:
            print(f"Error getting bot user info: {str(e)}")
            return
        
        while True:
            try:
                # Get new mentions
                mentions = self.get_new_mentions()
                
                for mention in mentions:
                    try:
                        print(f"Processing mention: {mention.text}")
                        
                        # Extract URLs from mention text
                        import re
                        urls = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', mention.text)
                        
                        if urls:
                            video_url = urls[0]
                            print(f"Found URL: {video_url}")
                            
                            # Process video (implement your video processing here)
                            # ...
                            
                        else:
                            print(f"No URL found in mention: {mention.id}")
                            
                    except Exception as e:
                        print(f"Error processing mention {mention.id}: {str(e)}")
                        continue
                
                # Wait before next check (respect rate limits)
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                print(f"Error in main loop: {str(e)}")
                time.sleep(60)  # Wait before retry
    def start(self):
        """Starts the bot"""
        self.run()
        
    def download_video_audio(self, video_url):
        """Downloads audio from video URL and returns the path"""
        try:
            yt = YouTube(video_url)
            audio_stream = yt.streams.filter(only_audio=True).first()
            
            temp_dir = tempfile.mkdtemp()
            temp_path = os.path.join(temp_dir, "temp_audio.mp3")
            
            audio_stream.download(filename=temp_path)
            return temp_path
        except Exception as e:
            print(f"Error downloading video: {str(e)}")
            return None

    def transcribe_video(self, audio_path):
        """Transcribes video audio using Replicate's Whisper model"""
        try:
            output = self.replicate_client.run(
                "vaibhavs10/incredibly-fast-whisper:3ab86df6c8f54c11309d4d1f930ac292bad43ace52d10c80d87eb258b3c9f79c",
                input={
                    "audio": open(audio_path, "rb"),
                    "language": "auto",
                    "model_name": "large-v3",
                    "temperature": 0,
                    "word_timestamps": False,
                }
            )
            return output['text']
        except Exception as e:
            print(f"Error transcribing video: {str(e)}")
            return None

    def create_summary(self, transcript):
        """Creates bullet-point summary using Replicate's BART model"""
        try:
            # Split long transcripts into chunks
            max_length = 1024
            chunks = [transcript[i:i+max_length] for i in range(0, len(transcript), max_length)]
            
            summaries = []
            for chunk in chunks:
                # Using meta/llama-2-70b-chat model for better summarization
                output = self.replicate_client.run(
                    "meta/llama-2-70b-chat:02e509c789964a7ea8736978a43525956ef40397be9033abf9fd2badfe68c9e3",
                    input={
                        "prompt": f"""Please provide a concise bullet-point summary of the following text. Focus on the key points and main ideas:

{chunk}

Format the response as bullet points starting with "•". Keep each bullet point brief and clear.""",
                        "temperature": 0.3,
                        "max_tokens": 500,
                        "top_p": 0.9,
                    }
                )
                
                # Clean up the summary and add bullet points
                summary = output.strip()
                if not summary.startswith("•"):
                    summary = "• " + summary
                summaries.append(summary)
            
            return "\n".join(summaries)
        except Exception as e:
            print(f"Error creating summary: {str(e)}")
            return None

    def save_transcript(self, transcript, summary, tweet_url):
        """Saves transcript as HTML and returns URL"""
        try:
            filename = self.transcript_formatter.format_transcript(transcript, summary, tweet_url)
            base_url = os.environ.get("BASE_URL", "http://localhost:5000")
            return f"{base_url}/transcript/{filename}"
        except Exception as e:
            print(f"Error saving transcript: {str(e)}")
            return None

    def extract_video_url(self, tweet):
        """Extracts video URL from tweet"""
        try:
            if tweet.includes and 'media' in tweet.includes:
                for media in tweet.includes['media']:
                    if media.type == 'video':
                        return media.url
            return None
        except Exception as e:
            print(f"Error extracting video URL: {str(e)}")
            return None