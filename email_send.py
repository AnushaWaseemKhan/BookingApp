import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(name,date,time,recipient_email,smtp_server="smtp.gmail.com",subject="Appointment Confirmation", port=587, sender_email='AnushaWaseemkhan@gmail.com', sender_password="bruh ufzd bgkm cbhf"):
    email_body=f"""
    Dear {name},

    Thank you for booking your appointment with us. This email is to confirm your appointment as follows:

    Date: {date}
    Time: {time}

    Please let us know if you have any specific requirements or if there is any change in your availability. We look forward to assisting you.

    Best regards,
    Cloud Design Lab
    """



    try:
        # Create a multipart message
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = recipient_email
        message['Subject'] = subject

        # Attach the email body
        message.attach(MIMEText(email_body, 'plain'))

        # Connect to the SMTP server and send the email
        with smtplib.SMTP(smtp_server, port) as server:
            server.starttls()  # Upgrade to secure connection
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, message.as_string())

        print(f"Email sent successfully to {recipient_email}.")

    except Exception as e:
        print(f"Failed to send email to {recipient_email}. Error: {e}")

# Example usage