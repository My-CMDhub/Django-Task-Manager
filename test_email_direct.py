import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_test_email():
    # Your Gmail credentials
    sender_email = "***REMOVED***"
    password = "***REMOVED***" # App password
    receiver_email = "***REMOVED***"
    
    # Create the email
    message = MIMEMultipart()
    message["From"] = f"Task Manager <{sender_email}>"
    message["To"] = receiver_email
    message["Subject"] = "SMTP Test Email"
    
    # Add body to email
    body = """
    This is a test email to verify SMTP settings are working.
    
    If you received this, your SMTP settings are correct!
    """
    message.attach(MIMEText(body, "plain"))
    
    try:
        # Connect to Gmail SMTP server with SSL
        print("Connecting to SMTP server...")
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.ehlo()
        
        # Login
        print("Logging in...")
        server.login(sender_email, password)
        print("Login successful!")
        
        # Send email
        print("Sending email...")
        server.sendmail(sender_email, receiver_email, message.as_string())
        print("Email sent successfully!")
        
        # Quit the server
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

if __name__ == "__main__":
    send_test_email() 