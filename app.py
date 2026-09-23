from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token
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
        license_plate = data.get("license_plate", "")
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
        x.send_email(email, html)

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

############################# api-login ##############################
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

    if not email or not password:
        return jsonify({"message": "Email og adgangskode skal udfyldes"}), 400

    db, cursor = x.db()
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if not user or not check_password_hash(user["password_hash"], password):
            return jsonify({"message": "Forkert email eller adgangskode"}), 401

        if not user["verified_at"]:
            return jsonify({"message": "Bekræft venligst din email før du kan logge ind"}), 403

        # access_token = create_access_token(identity=user["user_id"])
        access_token = create_access_token(identity=str(user["user_id"]))

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

    except Exception as ex:
        print(ex, flush=True)
        return jsonify({"message": "Login fejlede"}), 500

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
            x.send_email(email, html)

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
    except Exception:
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