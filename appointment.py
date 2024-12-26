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
        # Parse the payload
        payload = request.get_json() or request.form.to_dict() or request.data.decode('utf-8')
        if not payload:
            raise ValueError("Payload is empty or invalid.")

        # Extract arguments from the payload
        args = payload.get('message', {}).get('toolCalls', [])[0].get('function', {}).get('arguments', {})
        tool_call_id = payload.get('message', {}).get('toolCalls', [])[0].get('id')

        # Extract required details
        name = args.get('Name')
        email = args.get('Email')
        phone = args.get('Phone')
        purpose = args.get('Purpose')
        date = args.get('Date')
        time = args.get('Time')

        # Validate required fields
        if not all([name, email, phone, purpose, date, time]):
            raise ValueError("Missing required fields in the payload.")

        # Save data to Google Sheets
        try:
            data = [[name, email, phone, purpose, date, time]]
            google_sheet(data)
            print("Data successfully appended to Google Sheet.")
        except Exception as sheet_error:
            print(f"Error updating Google Sheet: {sheet_error}")

        # Send email confirmation
        try:
            send_email(name, date, time, email)
            print("Email successfully sent to", email)
        except Exception as email_error:
            print(f"Error sending email: {email_error}")

        # Send WhatsApp confirmation
        whatsapp_result = "WhatsApp notification skipped."
        if phone and phone.strip() and phone.startswith('+'):
            try:
                client.messages.create(
                    from_=TWILIO_WHATSAPP_NUMBER,
                    body=f"Hello {name}, your appointment is confirmed for {date} at {time}.",
                    to=f"whatsapp:{phone.strip()}"
                )
                whatsapp_result = "WhatsApp notification sent successfully."
            except TwilioRestException as e:
                if e.code == 63016:  # Error code for "No WhatsApp account"
                    whatsapp_result = "Phone number provided does not have WhatsApp."
                else:
                    raise  # Re-raise other Twilio exceptions
        else:
            whatsapp_result = "Invalid phone number provided for WhatsApp."

        # Construct final response
        return jsonify({
            'results': [{
                'toolCallId': tool_call_id,
                'result': f"Appointment booked successfully. {whatsapp_result}"
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
