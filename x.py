from flask import request, make_response                       # request = the data the browser sent in; make_response = build the answer we send back
import mysql.connector                                         # library that connects Flask to MariaDB, so we can run SQL queries
import os                                                      # let's python talk to the operating system (your mac): file paths, folders, environment variables
import re                                                      # regular expressions: check that text matches a pattern (e.g. a valid email)
from datetime import datetime                                  # get and format dates/times
from functools import wraps                                    # used when writing decorators (e.g. @login_required) so the wrapped function keeps its name

import uuid                                                    # generate unique random IDs
from werkzeug.utils import secure_filename                     # cleans uploaded filenames so they're safe to save

from icecream import ic                                        # Debugging tool that shows the name and the value.
                                                               # from icecream means “go to the package called icecream”.
                                                               # import ic means “bring me only the tool called ic”.

ic.configureOutput(prefix=f"_____ | ", includeContext=True)    # sets how ic() text looks in the terminal: starts with "_____ | " and shows file + line

import smtplib                                                 # smtplib: connects to a mail server
from email.mime.multipart import MIMEMultipart                 # MIMEMultipart: an empty email “envelope”
from email.mime.text import MIMEText                           # MIMEText: the email’s content


############ Function that connects Flask to MariaDB ##################
def db():
    try:
        db = mysql.connector.connect(
            host="mariadb",                                     # Flask finds MariaDB by its service name on the network: nextjs_test_backend_default 
            user="root",
            password=os.environ.get("DB_PASSWORD", "password"), # why is it written like this - to keep the real password out of the code
            database="ww_reeksamen"
        )
        cursor = db.cursor(dictionary=True)                     # Creates the order slip with rows returned as dictionaries instead of tuples
        return db, cursor                                       # Hands back the database connection and the order slip to the route in app.py 
    except Exception as e:
        print(e, flush=True)
        raise Exception("Database under maintenance", 500)


############### NO_CACHE #####################
# function - runs only if and when you call it
def no_cache(view):
    @wraps(view)
    def no_cache_view(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    return no_cache_view

############### RULES (VALIDATION): #####################
############# USER_NAME VALIDATION RULE #################
USER_NAME_MIN = 2
USER_NAME_MAX = 20
REGEX_USER_NAME = f"^.{{{USER_NAME_MIN},{USER_NAME_MAX}}}$"
def validate_user_name(user_name):
    user_name = user_name.strip()
    if not re.match(REGEX_USER_NAME, user_name):       # if the user name does NOT follow the rule...
        raise Exception("company_exception user_name") # ...stop and send an error (caught in app.py's except)
    return user_name

############## EMAIL VALIDATION RULE ################
REGEX_EMAIL = "^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$"
def validate_email(email):
    email = email.strip()
    if not re.match(REGEX_EMAIL, email):           # if the email does NOT follow the rule...
        raise Exception("company_exception email") # ...stop and send an error (caught in app.py's except)
    return email

############## USER_PHONE VALIDATION RULE ################
REGEX_USER_PHONE = "^(\+45)?\s?(\d{2}\s?){4}$"
def validate_user_phone(user_phone):
    user_phone = user_phone.strip()
    if not re.match(REGEX_USER_PHONE, user_phone):      # if the phone number does NOT follow the rule...
        raise Exception("company_exception user_phone") # ...stop and send an error (caught in app.py's except)
    return user_phone

########### USER_PASSWORD VALIDATION RULE ###################
USER_PASSWORD_MIN = 8
USER_PASSWORD_MAX = 50
REGEX_USER_PASSWORD = f"^.{{{USER_PASSWORD_MIN},{USER_PASSWORD_MAX}}}$"
def validate_user_password(password):
    if not re.match(REGEX_USER_PASSWORD, password):        # if the password does NOT follow the rule...
        raise Exception("company_exception user_password") # ...stop and send an error (caught in app.py's except)
    return password

############## UUID VALIDATION RULE ##################
# 0 to 9 letters a to f
REGEX_UUID4 = "^[0-9a-f]{32}$"
def validate_uuid4(uuid4):
    uuid_value = uuid4.strip()
    if not re.match(REGEX_UUID4, uuid_value):              # if the UUID does NOT follow the rule...
        raise Exception("company_exception uuid4 invalid") # ...stop and send an error (caught in app.py's except)
    return uuid_value

############# LICENSE_PLATE VALIDATION RULE ##################
LICENSE_PLATE_MIN = 2
LICENSE_PLATE_MAX = 10
REGEX_LICENSE_PLATE = f"^[A-Z0-9 ]{{{LICENSE_PLATE_MIN},{LICENSE_PLATE_MAX}}}$"
def validate_license_plate(license_plate):
    license_plate = license_plate.strip().upper()          # " ab12345 " → "AB12345"
    if not re.match(REGEX_LICENSE_PLATE, license_plate):   # if the plate does NOT follow the rule...
        raise Exception("company_exception license_plate") # ...stop and send an error (caught in app.py's except)
    return license_plate

############### EMAIL SECTION #####################
############# EMAIL SENDING #################
def send_email(receiver_email, html, subject="Wash World"):
        # subject="Wash World" → default value: calls that don't pass a subject still work
    try:
        # Create a gmail fullflaskdemomail
        # Enable (turn on) 2 step verification/factor in the google account manager
        # Visit: https://myaccount.google.com/apppasswords
        # Copy the key :
 
        # Email and password of the sender's Gmail account
        sender_email = os.environ.get("EMAIL_SENDER")
        password = os.environ.get("EMAIL_APP_PASSWORD")

        # Create the email message
        message = MIMEMultipart()                   # an empty email "envelope"
        message["From"] = "WashWorld Re-Exam"       # sender name shown in the inbox
        message["To"] = receiver_email              # who receives it
        message["Subject"] = subject                # now each route decides the subject

        message.attach(MIMEText(html, "html"))      # put the HTML content inside from the route in app.py line 87

        # Connect to Gmail's SMTP server and send the email
        with smtplib.SMTP("smtp.gmail.com", 587) as server:                     # connect to Gmail
            server.starttls()                                                   # Upgrade the connection to secure
            server.login(sender_email, password)                                # log in with .env values
            server.sendmail(sender_email, receiver_email, message.as_string())
            print("Email sent successfully!", flush=True)                       # confirmation in Docker logs

        return "email sent"

    except Exception as ex:
        ic(ex)                                      # print the error to the logs
        return "cannot send email", 500
    finally:
        pass

