from flask import Flask, request, jsonify

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
@app.route("/messages", methods = ['POST', 'GET'])
def handle_messages():
    if request.method == 'GET':
        #grabs challenge code sent through GET request
        challenge = request.args.get('challenge_code')
        #set endpoint url to include /handshake
        endpoint = f"{BASE_URL}/handshake"

        #call hashing functinon
        h = create_hash(challenge, VERIFICATION_TOKEN, endpoint)
        #respond with hashed challenge response in json format
        return jsonify({"challengeResponse": h}), 200
    
    if request.method == 'POST':
        try:
            xml_data = request.data
            data_dict = xmltodict.parse(xml_data)

            soap_body = data_dict.get('soapenv:Envelope', {}).get('soapenv:Body', {})
            notification = soap_body.get('GetMyMessagesResponse', {})

            print("!!! NEW MESSAGE RECEIVED !!!")
            print(notification)

            return "OK", 200
        
        except Exception as e:
            print(f"Error processing message: {e}")
            return "Error", 500



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
        endpoint = f"{BASE_URL}/handshake"

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