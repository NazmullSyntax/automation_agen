import os
import time
import requests
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pypdf import PdfReader
from openai import OpenAI

# Load configuration
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
WATCH_FOLDER = os.getenv("WATCH_FOLDER", "./incoming_docs")

client = OpenAI(api_key=OPENAI_API_KEY)

def extract_text(file_path: str) -> str:
    """Extract text from TXT or PDF files."""
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    
    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    elif ext == ".pdf":
        reader = PdfReader(file_path)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    return text.strip()

def summarize_content(text: str, filename: str) -> str:
    """Generate a concise executive summary using GPT-4o-mini."""
    if not text:
        return "No extractable text found in file."

    prompt = (
        f"You are an executive assistant. Summarize the following document titled '{filename}' "
        "into 3 bullet points, highlighting key actions, risks, or key takeaways:\n\n"
        f"{text[:4000]}"  # Truncated for safety
    )
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return response.choices[0].message.content

def send_slack_notification(filename: str, summary: str):
    """Post document summary directly to Slack."""
    payload = {
        "text": f"📄 *New Document Processed:* `{filename}`\n\n*Summary:*\n{summary}"
    }
    response = requests.post(SLACK_WEBHOOK_URL, json=payload)
    if response.status_status_code if hasattr(response, 'status_status_code') else response.status_code == 200:
        print(f"Successfully notified Slack for {filename}")
    else:
        print(f"Failed to send Slack alert: {response.text}")

class DocumentHandler(FileSystemEventHandler):
    """Monitor directory events and trigger AI pipeline."""
    def on_created(self, event):
        if event.is_directory:
            return
        
        file_path = event.src_path
        filename = os.path.basename(file_path)
        
        # Ignore hidden/temporary files
        if filename.startswith("."):
            return
            
        print(f"\n[Detected New File]: {filename}")
        time.sleep(1)  # Allow file write to complete
        
        try:
            text = extract_text(file_path)
            if text:
                print("Generating summary...")
                summary = summarize_content(text, filename)
                print("Sending notification...")
                send_slack_notification(filename, summary)
            else:
                print(f"Skipping empty or unreadable file: {filename}")
        except Exception as e:
            print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    if not os.path.exists(WATCH_FOLDER):
        os.makedirs(WATCH_FOLDER)

    event_handler = DocumentHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_FOLDER, recursive=False)
    observer.start()
    
    print(f"🚀 AI Automation Engine active! Monitoring: '{WATCH_FOLDER}'...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nStopping automation engine...")
    observer.join()