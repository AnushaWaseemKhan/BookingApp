from flask import Flask, request, jsonify
from twilio.rest import Client
from email_send import send_email
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from twilio.base.exceptions import TwilioRestException
import random
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()

# Twilio credentials from environment variables
ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_NUMBER = 'whatsapp:+14155238886'

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# Google Sheets API configuration
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1RLG7-V2z2dsRM7xm6Ydeerogybf4WFsRT5tuG1zEFzw"
RANGE_NAME = "Sheet1!A2:Z"

def google_sheet(data):
    """Appends a new row to the Google Sheet."""
    creds = None
    token_path = "token.json"

    # Load existing credentials or refresh them if expired
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing token: {e}")
                creds = None
        
        # Re-authenticate if refreshing fails or creds are invalid
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        # Save refreshed or newly authenticated credentials
        with open(token_path, "w") as token:
            token.write(creds.to_json())

    try:
        service = build("sheets", "v4", credentials=creds)
        body = {"values": data}
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME,
            valueInputOption="RAW",
            body=body,
            insertDataOption="INSERT_ROWS",
        ).execute()

        print("Data successfully appended to the spreadsheet.")
    except HttpError as err:
        print(f"An error occurred: {err}")

@app.route('/', methods=['POST'])
def print_payload():
    """Handles appointment booking."""
    try:
        payload = request.get_json()
        if not payload:
            payload = request.form.to_dict()
        if not payload:
            payload = request.data.decode('utf-8')

        args = payload.get('message', {}).get('toolCalls', [])[0].get('function', {}).get('arguments')
        tool_call_id = payload.get('message', {}).get('toolCalls', [])[0].get('id')

        name = args.get('Name')
        email = args.get('Email')
        phone = args.get('Phone') 
        purpose = args.get('Purpose')
        date = args.get('Date')
        time = args.get('Time')

        # Save to Google Sheets
        data = [[name, email, phone, purpose, date, time]]
        google_sheet(data)

        # Send email confirmation
        send_email(name, date, time, email)

        # Send WhatsApp confirmation
        try:
            client.messages.create(
                from_=TWILIO_WHATSAPP_NUMBER,
                body=f"Hello {name}, your appointment is confirmed for {date} at {time}.",
                to=f"whatsapp:{phone}"  # Use the phone number here
            )
        except TwilioRestException as e:
            if e.code == 63016:  # Error code for "No WhatsApp account"
                return jsonify({
                    'results': [{
                        'toolCallId': tool_call_id,
                        'result': "Appointment booked, but the phone number provided does not have WhatsApp."
                    }]
                }), 200
            else:
                raise  # Re-raise other Twilio exceptions

        return jsonify({
            'results': [{
                'toolCallId': tool_call_id,
                'result': "Appointment booked successfully"
            }]
        }), 200
    except Exception as e:
        print("Error processing payload:", e)
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/dates', methods=['POST'])
def get_date():
    """Returns random appointment slots."""
    payload = request.get_json()
    if not payload:
        payload = request.form.to_dict()
    if not payload:
        payload = request.data.decode('utf-8')

    args = payload.get('message', {}).get('toolCalls', [])[0].get('function', {}).get('arguments')
    tool_call_id = payload.get('message', {}).get('toolCalls', [])[0].get('id')

    now = datetime.now()
    end_date = now + timedelta(days=7)

    random_datetimes = []
    for _ in range(3):
        random_hours = random.randint(0, int((end_date - now).total_seconds() // 3600))
        random_datetime = now + timedelta(hours=random_hours)
        random_datetime = random_datetime.replace(minute=0, second=0, microsecond=0)
        random_datetimes.append(random_datetime.strftime("%Y-%m-%d %H:%M"))

    return jsonify({
        'results': [{
            'toolCallId': tool_call_id,
            'result': f"The available dates and time are: {random_datetimes}"
        }]
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))
