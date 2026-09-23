import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

sender_email = "charlieeskea@gmail.com"
password = "mmlf nbma nzcc mxmk"
receiver_email = "nyhedsbrifer@gmail.com"

message = MIMEMultipart()
message["From"] = sender_email
message["To"] = receiver_email
message["Subject"] = "Test"
message.attach(MIMEText("<p>This is a test.</p>", "html"))

with smtplib.SMTP("smtp.gmail.com", 587) as server:
    server.starttls()
    server.login(sender_email, password)
    server.sendmail(sender_email, receiver_email, message.as_string())

print("Email sent successfully!")
