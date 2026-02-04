from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy 
import threading
import re
import os
import hashlib
import xmltodict


app = Flask(__name__)

#load environment varialbes from .env file
load_dotenv()

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("SQL_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

#set up the database connection
db = SQLAlchemy(app)

#database model for clients
class Client(db.Model):
    __tablename__ = 'inventory'
    id = db.Column(db.BigInteger, primary_key=True)
    title = db.Column(db.String(100), nullable=False)

def get_item(item_id):
    item = Client.query.filter_by(id=item_id).first()
    if item:
        return {'id': item.id, 'title': item.title}
    
    return None     



#ngronk url for testing purposes (HTTPS to HTTP tunneling)
BASE_URL = os.getenv("BASE_URL")

#EBAY APP ID
APP_ID = os.getenv("APP_ID")


#special verification token I created
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN")

#hashing function using sha256
def create_hash(challenge, token, url):
    combined = challenge + token + url
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()

# Function to process incoming eBay messages using threads
def process_ebay_message(raw_xml_data):
    data_dict = xmltodict.parse(raw_xml_data)
    # Navigate the SOAP structure
    soap_envelope = data_dict.get('soapenv:Envelope', {})
    soap_body = soap_envelope.get('soapenv:Body', {})
    response = soap_body.get('GetMyMessagesResponse', {})
    messages_container = response.get('Messages', {})
    
    msg_data = messages_container.get('Message', [])
    if isinstance(msg_data, dict):
        msg_data = [msg_data]

    for msg in msg_data:
        sender = msg.get('Sender', 'Unknown')
        raw_html = msg.get('Text', '')
        itemID = msg.get('ItemID')
        
        # Heavy BeautifulSoup processing
        actual_message = extract_buyer_message(raw_html)
        
        print(f"Item ID: {itemID}")
        print(f"\n--- NEW MESSAGE FROM: {sender} ---")
        print(f"CONTENT: {actual_message}")
        print(f"----------------------------------\n")
        # Database query



# Function to extract buyer message from eBay HTML notification
def extract_buyer_message(raw_html):
    """
    Extract the actual buyer message from eBay's HTML notification.
    Tries multiple strategies to handle different HTML formats.
    """
    soup = BeautifulSoup(raw_html, 'html.parser')
    
    # Strategy 1: Look for "New message:" prefix
    message_p_tag = soup.find('p', string=lambda t: t and "New message:" in t)
    if message_p_tag:
        full_text = message_p_tag.get_text(strip=True)
        actual_message = full_text.replace("New message:", "").strip()
        if actual_message:
            return actual_message
    
    # Strategy 2: Look for specific patterns with regex
    # Sometimes the message is in a div or span after "New message:"
    text_content = soup.get_text(separator='\n')
    match = re.search(r'New message:\s*(.+?)(?:\n|Reply|$)', text_content, re.DOTALL)
    if match:
        actual_message = match.group(1).strip()
        if actual_message:
            return actual_message
    
    # Strategy 3: Find all paragraphs and filter out system text
    all_paragraphs = soup.find_all('p')
    for p in all_paragraphs:
        text = p.get_text(strip=True)
        # Skip common eBay system text
        if text and not any(skip in text.lower() for skip in [
            'reply', 'view message', 'go to my ebay', 'ebay inc', 
            'copyright', 'all rights reserved', 'questions about'
        ]):
            # If it contains "New message:", extract what's after it
            if "New message:" in text:
                return text.split("New message:")[-1].strip()
            # Otherwise, if it's substantial, it might be the message
            elif len(text) > 10:
                return text
    
    # Strategy 4: Look for the main content div/table
    # eBay often uses tables for layout
    main_content = soup.find('td', {'class': lambda x: x and 'content' in x.lower()})
    if not main_content:
        main_content = soup.find('div', {'class': lambda x: x and 'message' in x.lower()})
    
    if main_content:
        text = main_content.get_text(strip=True)
        # Remove the "New message:" prefix if present
        text = re.sub(r'^New message:\s*', '', text)
        # Remove common footers
        text = re.split(r'Reply|View message|Go to My eBay', text)[0].strip()
        if text:
            return text
    
    # Fallback: Return cleaned full text
    full_text = soup.get_text(separator=' ', strip=True)
    # Remove everything after common action words
    full_text = re.split(r'Reply|View message|Go to My eBay', full_text)[0]
    # Remove "New message:" if present
    full_text = re.sub(r'^New message:\s*', '', full_text)
    return full_text.strip()


# Example usage in your Flask endpoint:
# actual_message = extract_buyer_message(raw_html)


"""
This endpoint handles incoming messages that are received from EBAY users.
"""
@app.route("/messages", methods=['POST', 'GET'])
def handle_messages():
    if request.method == 'GET':
        challenge = request.args.get('challenge_code')
        endpoint = f"{BASE_URL}/messages"
        h = create_hash(challenge, VERIFICATION_TOKEN, endpoint)
        return jsonify({"challengeResponse": h}), 200
    
    if request.method == 'POST':
        raw_data = request.data

        task = threading.Thread(target=process_ebay_message, args = (raw_data,))
        task.start()

        return "OK", 200

"""
This endpoint is for handling account deletion requests from EBAY, 
which requires deleting user information from personal database.
"""
@app.route("/deletion", methods = ['POST', 'GET'])
def handle_deletion():
    if request.method == 'GET':
        #grabs challenge code sent through GET request
        challenge = request.args.get('challenge_code')
        #set endpoint url to include /handshake
        endpoint = f"{BASE_URL}/deletion"

        #call hashing functinon
        h = create_hash(challenge, VERIFICATION_TOKEN, endpoint)
        #respond with hashed challenge response in json format
        return jsonify({"challengeResponse": h}), 200
    
    #this is the post request handler that sends user data
    if request.method == 'POST':
        #pull json data from request
        data = request.get_json()

        if data:
            try:
                #pull user_id and username from json data, used to remove user data from database
                user_id = data['notification']['data']['userId']
                username = data['notification']['data']['username']

            #if no data, print error message
            except KeyError:
                print("Received POST but JSON structure was unexpected")

        return "OK", 200


"""
This endpoint is for handling handshake requests from EBAY (to ensure requests can be made)
"""
@app.route("/handshake", methods = ['POST', 'GET'])
def handle_handshake():
    if request.method == 'GET':
        #grabs challenge code sent through GET request
        challenge = request.args.get('challenge_code')
        #set endpoint url to include /handshake
        endpoint = f"{BASE_URL}/handshake"

        #call hashing functinon
        h = create_hash(challenge, VERIFICATION_TOKEN, endpoint)
        #respond with hashed challenge response in json format
        return jsonify({"challengeResponse": h}), 200
    
    #for POST requests, simply return OK
    return "OK", 200


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))

    app.run(host='0.0.0.0', port=port)