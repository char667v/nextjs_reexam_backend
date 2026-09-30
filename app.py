from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import os
import x

app = Flask(__name__)
CORS(app)

app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "dev-secret-change-me")
jwt = JWTManager(app)

########################### api-signup ###############################
@app.post("/api-signup")
def signup():
    try:
        data = request.json
        name = x.validate_user_name(data.get("user_name", ""))
        email = x.validate_email(data.get("user_email", ""))
        password = x.validate_user_password(data.get("user_password", ""))
        # license_plate = data.get("license_plate", "")
        license_plate = x.validate_license_plate(str(data.get("license_plate", ""))) #wrapping it in a validator
    except Exception:
        return jsonify({"message": "Ugyldige oplysninger"}), 400

    db, cursor = x.db()
    try:
        cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"message": "Email er allerede i brug"}), 409

        user_id = uuid.uuid4().hex
        verification_key = uuid.uuid4().hex
        password_hash = generate_password_hash(password)

        cursor.execute(
            """INSERT INTO users
               (user_id, name, email, password_hash, license_plate, verification_key)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (user_id, name, email, password_hash, license_plate, verification_key),
        )
        db.commit()

        verify_link = f"http://localhost:80/api-verify-email?key={verification_key}"
        html = f"""
            <p>Velkommen til Wash World, {name}!</p>
            <p>Bekræft din email for at aktivere din konto:</p>
            <a href="{verify_link}">Bekræft min email</a>
        """
        x.send_email(email, html, subject="Bekræft venligst din email")

        return jsonify({"message": "Bruger oprettet. Tjek din email for at bekræfte kontoen."}), 201

    except Exception as ex:
        print(ex, flush=True)
        return jsonify({"message": "Kunne ikke oprette bruger"}), 500

    finally:
        cursor.close()
        db.close()

######################### api-verify-email ###########################
@app.get("/api-verify-email")
def verify_email():
    try:
        key = x.validate_uuid4(request.args.get("key", ""))
    except Exception:
        return "<p>Ugyldigt bekræftelseslink.</p>", 400

    db, cursor = x.db()
    try:
        cursor.execute("SELECT user_id FROM users WHERE verification_key = %s", (key,))
        user = cursor.fetchone()

        if not user:
            return "<p>Bekræftelseslink ikke fundet.</p>", 404

        cursor.execute(
            "UPDATE users SET verified_at = NOW() WHERE user_id = %s",
            (user["user_id"],),
        )
        db.commit()

        return "<p>Din konto er nu bekræftet! Du kan nu logge ind.</p>", 200

    except Exception as ex:
        print(ex, flush=True)
        return "<p>Noget gik galt.</p>", 500

    finally:
        cursor.close()
        db.close()

###################### api-forgot-password ############################
@app.post("/api-forgot-password")
def forgot_password():
    data = request.json
    try:
        email = x.validate_email(data.get("user_email", ""))
    except Exception:
        return jsonify({"message": "Ugyldig email"}), 400

    db, cursor = x.db()
    try:
        cursor.execute("SELECT user_id, name FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user:
            reset_token = uuid.uuid4().hex
            cursor.execute(
                "UPDATE users SET reset_token = %s WHERE user_id = %s",
                (reset_token, user["user_id"]),
            )
            db.commit()

            reset_link = f"http://localhost:3000/pages/resetPassword?token={reset_token}"
            html = f"""
                <p>Hej {user['name']},</p>
                <p>Klik her for at nulstille din adgangskode:</p>
                <a href="{reset_link}">Nulstil min adgangskode</a>
            """
            x.send_email(email, html, subject="Nulstil din adgangskode")

        return jsonify({"message": "Hvis emailen findes, er der sendt et nulstillingslink"}), 200

    except Exception as ex:
        print(ex, flush=True)
        return jsonify({"message": "Noget gik galt"}), 500

    finally:
        cursor.close()
        db.close()

###################### api-reset-password ############################

@app.post("/api-reset-password")
def reset_password():
    data = request.json
    try:
        token = x.validate_uuid4(data.get("token", ""))
        new_password = x.validate_user_password(data.get("new_user_password", ""))
    # except Exception:
    #     return jsonify({"message": "Ugyldige oplysninger"}), 400
    except Exception as ex:
        print(ex, flush=True)          # NEW: print the real validator error to the Docker logs
        return jsonify({"message": "Ugyldige oplysninger"}), 400

    db, cursor = x.db()
    try:
        cursor.execute("SELECT user_id FROM users WHERE reset_token = %s", (token,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"message": "Linket er ugyldigt eller udløbet"}), 400

        password_hash = generate_password_hash(new_password)
        cursor.execute(
            "UPDATE users SET password_hash = %s, reset_token = NULL WHERE user_id = %s",
            (password_hash, user["user_id"]),
        )
        db.commit()

        return jsonify({"message": "Adgangskode nulstillet"}), 200

    except Exception as ex:
        print(ex, flush=True)
        return jsonify({"message": "Kunne ikke nulstille adgangskode"}), 500

    finally:
        cursor.close()
        db.close()

############################# api-login ##############################
# ── 1. HTTP REQUEST ARRIVES (arrow: frontend → backend) ──────────────
@app.post("/api-login")
def login():
    data = request.get_json(silent=True) or {}
    # request.get_json(...)  → "Hey request, give me your body as JSON"
    # silent=True            → if the body isn't JSON, don't crash, return None instead
    # or {}                  → if the result is None, use an empty dictionary
    # data                   → always a dictionary now, never None

    email = str(data.get("user_email", "")).strip()
    # data.get("user_email", "") → "Hey data, give me user_email, or "" if it's missing"
    # str(...)                   → make sure it's text, even if someone sent a number
    # .strip()                   → remove spaces from both ends: " a@b.dk " → "a@b.dk"
    # email                      → same name as before, so the rest of the code uses the clean value
    password = data.get("user_password", "")

# ── 2. BACKEND LOGIC: check the input (inside the backend box) ───────
    if not email or not password:
        return jsonify({"message": "Email og adgangskode skal udfyldes"}), 400
    try:                                                # NEW: check the rules
        email = x.validate_email(email)
        password = x.validate_user_password(password)
    except Exception:
        return jsonify({"message": "Ugyldig email eller adgangskode"}), 400

# ── 3. SQL QUERY (arrow: backend → database) ─────────────────────────
    db, cursor = x.db()                                 # only now: ask the database
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
# ── 4. ROWS BACK (arrow: database → backend) ─────────────────────────
        user = cursor.fetchone()
# ── 5. BACKEND LOGIC: decide the answer (inside the backend box) ─────
        if not user or not check_password_hash(user["password_hash"], password):
            return jsonify({"message": "Forkert email eller adgangskode"}), 401

        if not user["verified_at"]:
            return jsonify({"message": "Bekræft venligst din email før du kan logge ind"}), 403

        access_token = create_access_token(identity=str(user["user_id"]))
# ── 6. JSON RESPONSE (arrow: backend → frontend) ─────────────────────
        return jsonify({
            "access_token": access_token,
            "user": {
                "user_id": user["user_id"],
                "name": user["name"],
                "email": user["email"],
                "license_plate": user["license_plate"],
                "membership_tier": user["membership_tier"],
            },
        }), 200

# ── 7. SAFETY NET AND CLEANUP (backend only) ─────────────────────────
    except Exception as ex:
        print(ex, flush=True)
        return jsonify({"message": "Login fejlede"}), 500

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
            "SELECT user_id, name, email, license_plate, membership_tier FROM users WHERE user_id = %s",
            (user_id,),
        )
        user = cursor.fetchone()

        if not user:
            return jsonify({"message": "Bruger ikke fundet"}), 404

        return jsonify({"user": user}), 200

    except Exception as ex:
        print(ex, flush=True)
        return jsonify({"message": "Kunne ikke hente bruger"}), 500

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
    license_plate = data.get("license_plate")
    membership_tier = data.get("membership_tier")

    if name is None and license_plate is None and membership_tier is None:
        return jsonify({"message": "Intet at opdatere"}), 400

    try:                                             # validate only what was sent
        if name is not None:
            name = x.validate_user_name(str(name))
        if license_plate is not None:
            license_plate = x.validate_license_plate(str(license_plate))
        if membership_tier is not None:
            membership_tier = str(membership_tier).strip()
            if membership_tier not in ["Guld", "Premium", "Brilliant"]:
                raise Exception("company_exception membership_tier")
    except Exception as ex:
        print(ex, flush=True)
        return jsonify({"message": "Ugyldige oplysninger"}), 400

    db, cursor = x.db()
    try:
        if name is not None:
            cursor.execute("UPDATE users SET name = %s WHERE user_id = %s", (name, user_id))
        if license_plate is not None:
            cursor.execute("UPDATE users SET license_plate = %s WHERE user_id = %s", (license_plate, user_id))
        if membership_tier is not None:
            cursor.execute("UPDATE users SET membership_tier = %s WHERE user_id = %s", (membership_tier, user_id))
        db.commit()                                  # save all changes at once

        return jsonify({"message": "Oplysninger opdateret"}), 200

    except Exception as ex:
        print(ex, flush=True)
        return jsonify({"message": "Kunne ikke opdatere oplysninger"}), 500

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
            return jsonify({"message": "Bruger ikke fundet"}), 404

        db.commit()                                              # both deletes are saved together
        return jsonify({"message": "Konto slettet"}), 200

    except Exception as ex:
        print(ex, flush=True)
        db.rollback()                                            # undo everything if anything failed
        return jsonify({"message": "Kunne ikke slette konto"}), 500

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
        return jsonify({"wash_halls": wash_halls}), 200

    except Exception as ex:
        print(ex, flush=True)
        return jsonify({"message": "Kunne ikke hente vaskehaller"}), 500

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
        print(ex, flush=True)
        return jsonify({"message": "Ugyldige oplysninger"}), 400

    db, cursor = x.db()
    try:
        cursor.execute("SELECT hall_id FROM wash_halls WHERE hall_id = %s", (hall_id,))
        if not cursor.fetchone():
            return jsonify({"message": "Vaskehal ikke fundet"}), 404

        wash_id = uuid.uuid4().hex
        cursor.execute(
            "INSERT INTO washes (wash_id, user_id, hall_id, tier) VALUES (%s, %s, %s, %s)",
            (wash_id, user_id, hall_id, tier),
        )
        db.commit()
        return jsonify({"wash_id": wash_id}), 201

    except Exception as ex:
        print(ex, flush=True)
        return jsonify({"message": "Kunne ikke starte vask"}), 500

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
        return jsonify({"washes": washes}), 200

    except Exception as ex:
        print(ex, flush=True)
        return jsonify({"message": "Kunne ikke hente vaskehistorik"}), 500

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
        print(ex, flush=True)
        return jsonify({"message": "Ugyldige oplysninger"}), 400

    db, cursor = x.db()
    try:
        cursor.execute(
            "UPDATE washes SET rating = %s WHERE wash_id = %s AND user_id = %s",
            (rating, wash_id, user_id),
        )
        # "Hey database, set this rating on this wash, but only if it belongs to this user"
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "Vask ikke fundet"}), 404

        return jsonify({"message": "Bedømmelse gemt"}), 200

    except Exception as ex:
        print(ex, flush=True)
        return jsonify({"message": "Kunne ikke gemme bedømmelse"}), 500

    finally:
        cursor.close()
        db.close()