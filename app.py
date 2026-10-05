from flask import Flask, render_template, request, jsonify 
import uuid
import x
import os
import time
from datetime import timedelta
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity

from flask_cors import CORS
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import x                                  
from icecream import ic
ic.configureOutput(prefix=f"_____ | ", includeContext=True)

app = Flask(__name__)
CORS(app)# allows everything
# app.config['SESSION_TYPE'] = 'filesystem'
# Session(app)
app.config["JWT_SECRET_KEY"] = os.environ["JWT_SECRET_KEY"]
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=20)
jwt = JWTManager(app)

########################### health check ###########################
@app.get("/")
def index():
    return jsonify({"status": "ok", "message": "Connected and running"}), 200
# visible in the browser at http://localhost:80

########################### api-signup ###########################
@app.post("/api-signup")
def signup():
    try:
        data = request.get_json(silent=True) or {}
        name = x.validate_user_name(data.get("user_name", ""))
        email = x.validate_email(data.get("user_email", ""))
        password = x.validate_user_password(data.get("user_password", ""))
        # license_plate = data.get("license_plate", "")                                ← OLD: no validation (inactive)
        license_plate = x.validate_license_plate(str(data.get("license_plate", "")))  # wrapping it in a validator   ← NEW: validated (active)
        phone = data.get("user_phone")
        if phone:
            phone = x.validate_user_phone(str(phone))
        else:
            phone = None
        membership_tier = str(data.get("membership_tier", "Guld")).strip()
        if membership_tier not in ["Guld", "Premium", "Brilliant"]:
            raise Exception("company_exception membership_tier")

    except Exception as ex:
        ic(ex)
        if "company_exception user_name" in str(ex):
            return jsonify({"status": "error", "message": f"Navn skal være {x.USER_NAME_MIN}–{x.USER_NAME_MAX} tegn"}), 400
        if "company_exception email" in str(ex):
            return jsonify({"status": "error", "message": "Ugyldig email"}), 400
        if "company_exception user_password" in str(ex):
            return jsonify({"status": "error", "message": f"Adgangskoden skal være {x.USER_PASSWORD_MIN}–{x.USER_PASSWORD_MAX} tegn"}), 400
        if "company_exception license_plate" in str(ex):
            return jsonify({"status": "error", "message": f"Nummerpladen skal være {x.LICENSE_PLATE_MIN}–{x.LICENSE_PLATE_MAX} tegn"}), 400
        if "company_exception user_phone" in str(ex):
            return jsonify({"status": "error", "message": "Ugyldigt telefonnummer"}), 400
        if "company_exception membership_tier" in str(ex):
            return jsonify({"status": "error", "message": "Ugyldigt medlemskab"}), 400
        return jsonify({"status": "error", "message": "Ugyldige oplysninger"}), 400

    db, cursor = x.db()
    try:
        cursor.execute("SELECT user_id, user_name FROM users WHERE user_email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"status": "error", "message": "Email er allerede i brug"}), 409

        user_id = uuid.uuid4().hex
        verification_key = uuid.uuid4().hex
        password_hash = generate_password_hash(password)

        cursor.execute(
            """INSERT INTO users
               (user_id, user_name, user_email, user_password_hash, license_plate, verification_key, user_phone, membership_tier)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (user_id, name, email, password_hash, license_plate, verification_key, phone, membership_tier),
        )
        db.commit()

        verify_link = f"http://localhost:80/api-verify-email?key={verification_key}"
        html = render_template("email_signup.html", name=name, verify_link=verify_link)
        x.send_email(email, html, subject="Bekræft venligst din email")

        return jsonify({"status": "ok", "message": "Bruger oprettet. Tjek din email for at bekræfte kontoen."}), 201

    except Exception as ex:
        ic(ex)
        return jsonify({"status": "error", "message": "Kunne ikke oprette bruger"}), 500

    finally:
        cursor.close()
        db.close()

######################### api-verify-email ###########################
@app.get("/api-verify-email")
def verify_email():
    try:
        key = x.validate_uuid4(request.args.get("key", ""))
    except Exception:
        return jsonify({"status": "error", "message": "Ugyldigt bekræftelseslink"}), 400

    db, cursor = x.db()
    try:
        cursor.execute(
            "UPDATE users SET verified_at = NOW() WHERE verification_key = %s AND verified_at IS NULL",
            (key,),
        )
        # "Hey database, verify the user with this key, but only if not verified already"
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"status": "error", "message": "Linket er ugyldigt eller allerede brugt"}), 404

        return jsonify({"status": "ok", "message": "Din konto er nu bekræftet! Du kan nu logge ind."}), 200

    except Exception as ex:
        ic(ex)
        return jsonify({"status": "error", "message": "Noget gik galt"}), 500

    finally:
        cursor.close()
        db.close()

###################### api-forgot-password ############################
@app.post("/api-forgot-password")
def forgot_password():
    data = request.get_json(silent=True) or {}
    try:
        email = x.validate_email(data.get("user_email", ""))
    except Exception:
        return jsonify({"status": "error", "message": "Ugyldig email"}), 400

    db, cursor = x.db()
    try:
        cursor.execute("SELECT user_id, user_name FROM users WHERE user_email = %s", (email,))
        user = cursor.fetchone()

        if user:
            reset_token = uuid.uuid4().hex
            cursor.execute(
                "UPDATE users SET reset_token = %s WHERE user_id = %s",
                (reset_token, user["user_id"]),
            )
            db.commit()

            reset_link = f"http://localhost:3000/pages/resetPassword?token={reset_token}"
            html = render_template("email_forgot_password.html", name=user["user_name"], reset_link=reset_link)
            x.send_email(email, html, subject="Nulstil din adgangskode")

        return jsonify({"status": "ok", "message": "Hvis emailen findes, er der sendt et nulstillingslink"}), 200

    except Exception as ex:
        ic(ex)
        return jsonify({"status": "error", "message": "Noget gik galt"}), 500

    finally:
        cursor.close()
        db.close()

###################### api-reset-password ############################

@app.post("/api-reset-password")
def reset_password():
    data = request.get_json(silent=True) or {}
    try:
        token = x.validate_uuid4(data.get("token", ""))
        new_password = x.validate_user_password(data.get("new_user_password", ""))
    except Exception as ex:
        ic(ex)
        if "company_exception user_password" in str(ex):
            return jsonify({"status": "error", "message": f"Adgangskoden skal være {x.USER_PASSWORD_MIN}–{x.USER_PASSWORD_MAX} tegn"}), 400
        return jsonify({"status": "error", "message": "Linket er ugyldigt eller udløbet"}), 400

    db, cursor = x.db()
    try:
        password_hash = generate_password_hash(new_password)
        cursor.execute(
            "UPDATE users SET user_password_hash = %s, reset_token = NULL WHERE reset_token = %s",
            (password_hash, token),
        )
        # "Hey database, set this new password on the user with this token, and use up the token"
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"status": "error", "message": "Linket er ugyldigt eller udløbet"}), 400

        return jsonify({"status": "ok", "message": "Adgangskode nulstillet"}), 200

    except Exception as ex:
        ic(ex)
        return jsonify({"status": "error", "message": "Kunne ikke nulstille adgangskode"}), 500

    finally:
        cursor.close()
        db.close()

############################# api-login ##############################
# ── 1. HTTP REQUEST ARRIVES (arrow: frontend → backend) ──────────────
@app.post("/api-login")
def login():
    data = request.get_json(silent=True) or {}

    email = str(data.get("user_email", "")).strip()
 
    password = data.get("user_password", "")

# ── 2. BACKEND LOGIC: check the input (inside the backend box) ───────
    if not email or not password:
        return jsonify({"status": "error", "message": "Email og adgangskode skal udfyldes"}), 400
    try:                                                # NEW: check the rules
        email = x.validate_email(email)
        password = x.validate_user_password(password)
    except Exception:
        return jsonify({"status": "error", "message": "Ugyldig email eller adgangskode"}), 400

# ── 3. SQL QUERY (arrow: backend → database) ─────────────────────────
    db, cursor = x.db()                                 # only now: ask the database
    try:
        cursor.execute("SELECT * FROM users WHERE user_email = %s", (email,))
# ── 4. ROWS BACK (arrow: database → backend) ─────────────────────────
        user = cursor.fetchone()
# ── 5. BACKEND LOGIC: decide the answer (inside the backend box) ─────
        if not user or not check_password_hash(user["user_password_hash"], password):
            return jsonify({"status": "error", "message": "Forkert email eller adgangskode"}), 401

        if not user["verified_at"]:
            return jsonify({"status": "error", "message": "Bekræft venligst din email før du kan logge ind"}), 403

        access_token = create_access_token(identity=str(user["user_id"]))
# ── 6. JSON RESPONSE (arrow: backend → frontend) ─────────────────────
        return jsonify({
            "status": "ok",
            "access_token": access_token,
            "user": {
                "user_id": user["user_id"],
                "user_name": user["user_name"],
                "user_email": user["user_email"],
                "license_plate": user["license_plate"],
                "membership_tier": user["membership_tier"],
            },
        }), 200

# ── 7. SAFETY NET AND CLEANUP (backend only) ─────────────────────────
    except Exception as ex:
        ic(ex)
        return jsonify({"status": "error", "message": "Login fejlede"}), 500

    finally:
        cursor.close()
        db.close()


###################### api-my-info ############################
# The data source the profile section uses
# The profile page decides how it looks: the layout, colors, and components.
# /api-my-info decides what it shows: the actual data about the logged-in user

@app.get("/api-my-info")
@jwt_required()
def get_my_info():

    user_id = get_jwt_identity()

    db, cursor = x.db()
    try:
        cursor.execute(
        "SELECT user_id, user_name, user_email, license_plate, user_phone, membership_tier FROM users WHERE user_id = %s",
            (user_id,),
        )
        user = cursor.fetchone()

        if not user:
            return jsonify({"status": "error", "message": "Bruger ikke fundet"}), 404

        return jsonify({"status": "ok", "user": user}), 200

    except Exception as ex:
        ic(ex)
        return jsonify({"status": "error", "message": "Kunne ikke hente bruger"}), 500

    finally:
        cursor.close()
        db.close()

######################### api-update-my-info #########################
@app.patch("/api-update-my-info")
@jwt_required()
def update_my_info():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    name = data.get("user_name")                     # None if not sent
    phone = data.get("user_phone")                   
    license_plate = data.get("license_plate")
    membership_tier = data.get("membership_tier")

    if name is None and license_plate is None and membership_tier is None and phone is None:
        return jsonify({"status": "error", "message": "Intet at opdatere"}), 400

    try:                                             # validate only what was sent
        if name is not None:
            name = x.validate_user_name(str(name))
        if phone is not None:                                       
            phone = x.validate_user_phone(str(phone))
        if license_plate is not None:
            license_plate = x.validate_license_plate(str(license_plate))
        if membership_tier is not None:
            membership_tier = str(membership_tier).strip()
            if membership_tier not in ["Guld", "Premium", "Brilliant"]:
                raise Exception("company_exception membership_tier")
    except Exception as ex:
        ic(ex)
        if "company_exception user_name" in str(ex):
            return jsonify({"status": "error", "message": f"Navn skal være {x.USER_NAME_MIN}–{x.USER_NAME_MAX} tegn"}), 400
        if "company_exception user_phone" in str(ex):
            return jsonify({"status": "error", "message": "Ugyldigt telefonnummer"}), 400
        if "company_exception license_plate" in str(ex):
            return jsonify({"status": "error", "message": f"Nummerpladen skal være {x.LICENSE_PLATE_MIN}–{x.LICENSE_PLATE_MAX} tegn"}), 400
        if "company_exception membership_tier" in str(ex):
            return jsonify({"status": "error", "message": "Ugyldigt medlemskab"}), 400
        return jsonify({"status": "error", "message": "Ugyldige oplysninger"}), 400

    db, cursor = x.db()
    try:
        db.start_transaction()                       # 2 or more updates: all or nothing
        if name is not None:
            cursor.execute("UPDATE users SET user_name = %s WHERE user_id = %s", (name, user_id))
        if phone is not None:                                      
            cursor.execute("UPDATE users SET user_phone = %s WHERE user_id = %s", (phone, user_id))
        if license_plate is not None:
            cursor.execute("UPDATE users SET license_plate = %s WHERE user_id = %s", (license_plate, user_id))
        if membership_tier is not None:
            cursor.execute("UPDATE users SET membership_tier = %s WHERE user_id = %s", (membership_tier, user_id))
        db.commit()                                  # save all changes at once

        return jsonify({"status": "ok", "message": "Oplysninger opdateret"}), 200

    except Exception as ex:
        ic(ex)
        db.rollback()                                # undo everything if anything failed
        return jsonify({"status": "error", "message": "Kunne ikke opdatere oplysninger"}), 500

    finally:
        cursor.close()
        db.close()

######################## api-delete-account ##########################
@app.delete("/api-delete-account")
@jwt_required()
def delete_account():
    user_id = get_jwt_identity()

    db, cursor = x.db()
    try:
        db.start_transaction()                                   # start: "all or nothing"

        cursor.execute("DELETE FROM washes WHERE user_id = %s", (user_id,))
        # "Hey database, delete this user's washes" (first, because of the foreign key)

        cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        # "Hey database, delete the user"

        if cursor.rowcount == 0:                                 # no user was deleted
            db.rollback()
            return jsonify({"status": "error", "message": "Bruger ikke fundet"}), 404

        db.commit()                                              # both deletes are saved together
        return jsonify({"status": "ok", "message": "Konto slettet"}), 200

    except Exception as ex:
        ic(ex)
        db.rollback()                                            # undo everything if anything failed
        return jsonify({"status": "error", "message": "Kunne ikke slette konto"}), 500

    finally:
        cursor.close()
        db.close()

####################          WASH          ##########################
############################ api-wash-halls ##########################
@app.get("/api-wash-halls")
def get_wash_halls():
    db, cursor = x.db()
    try:
        cursor.execute("SELECT hall_id, name, address FROM wash_halls")
        wash_halls = cursor.fetchall()
        return jsonify({"status": "ok", "wash_halls": wash_halls}), 200

    except Exception as ex:
        ic(ex)
        return jsonify({"status": "error", "message": "Kunne ikke hente vaskehaller"}), 500

    finally:
        cursor.close()
        db.close()

############################ api-start-wash ##########################
@app.post("/api-start-wash")
@jwt_required()
def start_wash():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    try:
        hall_id = x.validate_uuid4(str(data.get("hall_id", "")))
        tier = str(data.get("tier", "")).strip()
        if tier not in ["Guld", "Premium", "Brilliant"]:
            raise Exception("company_exception tier")
    except Exception as ex:
        ic(ex)
        return jsonify({"status": "error", "message": "Ugyldige oplysninger"}), 400

    db, cursor = x.db()
    try:
        cursor.execute("SELECT hall_id FROM wash_halls WHERE hall_id = %s", (hall_id,))
        if not cursor.fetchone():
            return jsonify({"status": "error", "message": "Vaskehal ikke fundet"}), 404

        wash_id = uuid.uuid4().hex
        cursor.execute(
            "INSERT INTO washes (wash_id, user_id, hall_id, tier) VALUES (%s, %s, %s, %s)",
            (wash_id, user_id, hall_id, tier),
        )
        db.commit()
        return jsonify({"status": "ok", "wash_id": wash_id}), 201

    except Exception as ex:
        ic(ex)
        return jsonify({"status": "error", "message": "Kunne ikke starte vask"}), 500

    finally:
        cursor.close()
        db.close()

######################### api-my-wash-history ########################
@app.get("/api-my-wash-history")
@jwt_required()
def get_my_wash_history():
    user_id = get_jwt_identity()

    db, cursor = x.db()
    try:
        cursor.execute(
            # SELECT washes.wash_id, washes.tier, washes.washed_at, wash_halls.name AS hall_name
            """
            SELECT washes.wash_id, washes.tier, washes.washed_at, washes.rating, wash_halls.name AS hall_name
            FROM washes
            JOIN wash_halls ON wash_halls.hall_id = washes.hall_id
            WHERE washes.user_id = %s
            ORDER BY washes.washed_at DESC
            """,
            (user_id,),
        )
        # "Hey database, give me this user's washes, with the name of the hall, newest first"
        washes = cursor.fetchall()
        return jsonify({"status": "ok", "washes": washes}), 200

    except Exception as ex:
        ic(ex)
        return jsonify({"status": "error", "message": "Kunne ikke hente vaskehistorik"}), 500

    finally:
        cursor.close()
        db.close()

####################       WASH RATING      ##########################
############################ api-rate-wash ###########################

@app.patch("/api-rate-wash")
@jwt_required()
def rate_wash():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    try:
        wash_id = x.validate_uuid4(str(data.get("wash_id", "")))
        rating = int(data.get("rating", 0))
        if rating < 1 or rating > 5:
            raise Exception("company_exception rating")
    except Exception as ex:
        ic(ex)
        return jsonify({"status": "error", "message": "Ugyldige oplysninger"}), 400

    db, cursor = x.db()
    try:
        cursor.execute(
            "SELECT wash_id FROM washes WHERE wash_id = %s AND user_id = %s",
            (wash_id, user_id),
        )
        # "Hey database, does this wash exist, and does it belong to this user?"
        if not cursor.fetchone():
            return jsonify({"status": "error", "message": "Vask ikke fundet"}), 404

        cursor.execute("UPDATE washes SET rating = %s WHERE wash_id = %s", (rating, wash_id))
        db.commit()
        return jsonify({"status": "ok", "message": "Bedømmelse gemt"}), 200

    except Exception as ex:
        ic(ex)
        return jsonify({"status": "error", "message": "Kunne ikke gemme bedømmelse"}), 500

    finally:
        cursor.close()
        db.close()