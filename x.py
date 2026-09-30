from flask import request, make_response
import mysql.connector
import re 
from datetime import datetime
from functools import wraps
import os
import uuid
from werkzeug.utils import secure_filename
from icecream import ic
ic.configureOutput(prefix=f"_____ | ", includeContext=True)

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

##############################
def db():
    try:
        db = mysql.connector.connect(
            host="mariadb",
            user="root",
            password=os.environ.get("DB_PASSWORD", "password"), # why is it written like this?
            database="ww_reeksamen"
        )
        cursor = db.cursor(dictionary=True)
        return db, cursor
    except Exception as e:
        print(e, flush=True)
        raise Exception("Database under maintenance", 500)

############################## # Added line 32-43 from the old project
def no_cache(view):
    @wraps(view)
    def no_cache_view(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    return no_cache_view
#################
def format_epoch_date(epoch_value):
    return datetime.fromtimestamp(epoch_value).strftime("%Y-%m-%d")

##############################
USER_NAME_MIN = 2
USER_NAME_MAX = 20
REGEX_USER_NAME = f"^.{{{USER_NAME_MIN},{USER_NAME_MAX}}}$"
def validate_user_name(user_name):
    user_name = user_name.strip()
    if not re.match(REGEX_USER_NAME, user_name):
        raise Exception("company_exception user_name")
    return user_name

##############################
# USER_FIRST_NAME_MIN = 2
# USER_FIRST_NAME_MAX = 20
# REGEX_USER_FIRST_NAME = f"^.{{{USER_FIRST_NAME_MIN},{USER_FIRST_NAME_MAX}}}$"
# def validate_user_first_name(user_first_name):
#     user_first_name = user_first_name.strip()
#     if not re.match(REGEX_USER_FIRST_NAME, user_first_name):
#         raise Exception("company_exception user_first_name")
#     return user_first_name

# ##############################
# USER_LAST_NAME_MIN = 2
# USER_LAST_NAME_MAX = 20
# REGEX_USER_LAST_NAME = f"^.{{{USER_LAST_NAME_MIN},{USER_LAST_NAME_MAX}}}$"
# def validate_user_last_name(user_last_name):
#     user_last_name = user_last_name.strip()
#     if not re.match(REGEX_USER_LAST_NAME, user_last_name):
#         raise Exception("company_exception user_last_name")
#     return user_last_name

##############################
REGEX_EMAIL = "^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$"
def validate_email(email):
    email = email.strip()
    if not re.match(REGEX_EMAIL, email):
        raise Exception("company_exception email")
    return email

##############################
# USER_ADDRESS_MIN = 8
# USER_ADDRESS_MAX = 200
# REGEX_USER_ADDRESS =f"^.{{{USER_ADDRESS_MIN},{USER_ADDRESS_MAX}}}$"
# def validate_user_address(user_address):
#     user_address = user_address.strip()
#     if not re.match(REGEX_USER_ADDRESS, user_address):
#         raise Exception("company_exception user_address")
#     return user_address

##############################
REGEX_USER_PHONE = "^(\+45)?\s?(\d{2}\s?){4}$"
def validate_user_phone(user_phone):
    user_phone = user_phone.strip()
    if not re.match(REGEX_USER_PHONE, user_phone):
        raise Exception("company_exception user_phone")
    return user_phone

##############################
USER_PASSWORD_MIN = 8
USER_PASSWORD_MAX = 50
REGEX_USER_PASSWORD = f"^.{{{USER_PASSWORD_MIN},{USER_PASSWORD_MAX}}}$"
def validate_user_password(password):
    if not re.match(REGEX_USER_PASSWORD, password):
        raise Exception("company_exception user_password")
    return password

##############################
# 0 to 9 letters a to f
REGEX_UUID4 = "^[0-9a-f]{32}$"
def validate_uuid4(uuid4):
    uuid_value = uuid4.strip()
    if not re.match(REGEX_UUID4, uuid_value):
        raise Exception("company_exception uuid4 invalid")
    return uuid_value

##############################
REGEX_UUID4_PARANOIA = "^[0-9a-f]{64}$"
def validate_uuid4_paranoia(uuid4):
    uuid = uuid4.strip()
    if not re.match(REGEX_UUID4_PARANOIA, uuid):
        raise Exception("company_exception paranoia")
    return uuid

##############################
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

        message.attach(MIMEText(html, "html"))      # put the HTML content inside

        # Connect to Gmail's SMTP server and send the email
        with smtplib.SMTP("smtp.gmail.com", 587) as server:  # connect to Gmail
            server.starttls() # Upgrade the connection to secure
            server.login(sender_email, password)              # log in with .env values
            server.sendmail(sender_email, receiver_email, message.as_string())
            print("Email sent successfully!")                 # confirmation in Docker logs

        return "email sent"

    except Exception as ex:
        ic(ex)                                      # print the error to the logs
        return "cannot send email", 500
    finally:
        pass

##############################
REGEX_LICENSE_PLATE = "^[A-Z0-9 ]{2,10}$"
def validate_license_plate(license_plate):
    license_plate = license_plate.strip().upper()    # " ab12345 " → "AB12345"
    if not re.match(REGEX_LICENSE_PLATE, license_plate):
        raise Exception("company_exception license_plate")
    return license_plate