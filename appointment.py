from flask import Flask, request, jsonify
from email_send import send_email
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import random
from datetime import datetime, timedelta
app = Flask(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Replace with your Spreadsheet ID
SPREADSHEET_ID = "1RLG7-V2z2dsRM7xm6Ydeerogybf4WFsRT5tuG1zEFzw"
RANGE_NAME = "Sheet1!A2:Z"  # Range starting from row 2 (to skip headers)

def google_sheet(data):
    """Appends a new row to the Google Sheet every time the function is run."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        print('here')
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("sheets", "v4", credentials=creds)

        # Example data to append

        body = {
            "values": data
        }

        # Use the 'append' method to add the new row
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME,  # This should be the range from row 2 onwards
            valueInputOption="RAW",  # Write raw values
            body=body,
            insertDataOption="INSERT_ROWS",  # Ensures that new rows are inserted
        ).execute()

        print("Data successfully appended to the spreadsheet.")

    except HttpError as err:
        print(f"An error occurred: {err}")


@app.route('/', methods=['POST'])
def print_payload():
    try:
        # Attempt to get JSON data
        payload = request.get_json()
        if payload is None:
            # If no JSON, try to get form data
            payload = request.form.to_dict()
        
        if not payload:
            # If still no data, get raw data
            payload = request.data.decode('utf-8')
        
        # Print the payload to the console
        # print("Received Payload:", payload.get('message', {}).get('toolCalls', [])[0].get('function', {}).get('arguments'))
        # print("Received Payload Type:", type(payload.get('message', {}).get('toolCalls', [])[0].get('function', {}).get('arguments')))
        args=payload.get('message', {}).get('toolCalls', [])[0].get('function', {}).get('arguments')
        tool_call_id = payload.get('message', {}).get('toolCalls', [])[0].get('id')
        data=[[args.get('Name'),args.get('Email'),args.get('Purpose'),args.get('Date'),args.get('Time')]]
        google_sheet(data)
        # Optionally, return the payload in the response
        print(args)
        send_email(args.get('Name'),args.get('Date'),args.get('Time'),args.get('Email'))
        return jsonify({'results':[
        {
        'toolCallId': tool_call_id,
        'result': f"Appointment booked successfully"
        }
        ]
        }
        ), 200

    except Exception as e:
        print("Error processing payload:", e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


@app.route('/dates', methods=['POST'])
def get_date():
    payload = request.get_json()
    if payload is None:
        # If no JSON, try to get form data
        payload = request.form.to_dict()
    
    if not payload:
        # If still no data, get raw data
        payload = request.data.decode('utf-8')
    
    args=payload.get('message', {}).get('toolCalls', [])[0].get('function', {}).get('arguments')
    tool_call_id = payload.get('message', {}).get('toolCalls', [])[0].get('id')
    print(tool_call_id)

    now = datetime.now()
    end_date = now + timedelta(days=7)
    
    random_datetimes = []
    for _ in range(3):
        # Generate a random number of hours between now and one week from now
        random_hours = random.randint(0, int((end_date - now).total_seconds() // 3600))
        random_datetime = now + timedelta(hours=random_hours)
        # Set the minutes and seconds to zero for hour-only precision
        random_datetime = random_datetime.replace(minute=0, second=0, microsecond=0)
        random_datetimes.append(random_datetime.strftime("%Y-%m-%d %H:%M"))
    return jsonify({'results':[
    {
    'toolCallId': tool_call_id,
    'result': f"The available dates and time are: {random_datetimes}"
    }
    ]
    }
    ), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))
