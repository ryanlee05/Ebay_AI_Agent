from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os
import hashlib
import xmltodict


app = Flask(__name__)

#load environment varialbes from .env file
load_dotenv()

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
        try:
            # Parse the XML raw data
            data_dict = xmltodict.parse(request.data)
            
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
                
                soup = BeautifulSoup(raw_html, 'html.parser')

                # 1. Target the <p> tag that contains the text "New message:"
                # We use a lambda function to find a p tag where "New message:" is in the text
                message_p_tag = soup.find('p', text=lambda t: t and "New message:" in t)
                
                if message_p_tag:
                    full_text = message_p_tag.get_text(strip=True)
                    # This removes the "New message: " part so you only get "Hey can I come pick this up?"
                    actual_message = full_text.replace("New message:", "").strip()
                else:
                    # Fallback: if they change the format, just grab the first div with content
                    actual_message = soup.get_text(separator=' ', strip=True).split('Reply')[0]

                print(f"\n--- NEW MESSAGE FROM: {sender} ---")
                print(f"CONTENT: {actual_message}")
                print(f"----------------------------------\n")

            return "OK", 200

        except Exception as e:
            print(f"Error processing message: {e}")
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
                
                print(f"!!! DELETION REQUEST RECEIVED !!!")
                print(f"User ID: {user_id}")
                print(f"Username: {username}")

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