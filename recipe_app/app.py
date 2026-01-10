from flask import Flask, render_template, request, jsonify, session,redirect
from config import Config
from extensions import mysql, bcrypt
from datetime import datetime, timedelta
import secrets
app = Flask(__name__)

app.config.from_object(Config)

mysql.init_app(app)
bcrypt.init_app(app)

@app.route("/")
def index():
    if "user_id" in session:
        return redirect("/dashboard")
    return render_template("index.html")

# ================= REGISTER =================
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")

    conn = mysql.connect()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
    if cursor.fetchone():
        return jsonify({"success": False, "message": "Email already exists"})

    cursor.execute(
        "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
        (username, email, hashed_pw)
    )
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"success": True})

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return render_template("index.html") 
    return render_template("dashboard.html", username=session["username"])

# ================= LOGIN =================
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("username")
    password = data.get("password")

    conn = mysql.connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, username, password FROM users WHERE email=%s", (email,)
    )
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if user and bcrypt.check_password_hash(user[2], password):
        session["user_id"] = user[0]
        session["username"] = user[1]
        return jsonify({"success": True})

    return jsonify({"success": False, "message": "Invalid credentials"})

# ================= CHECK AUTH =================
@app.route("/api/check-auth")
def check_auth():
    if "user_id" in session:
        return jsonify({
            "is_logged_in": True,
            "user": {"username": session["username"]}
        })
    return jsonify({"is_logged_in": False})

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()      
    return redirect('/dashboard') 






@app.route("/api/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json()
    email = data.get("email")

    conn = mysql.connect()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()
        return jsonify({"success": True})  

   
    code = str(secrets.randbelow(1000000)).zfill(6)
    expires_at = datetime.now() + timedelta(minutes=10)


    cursor.execute("DELETE FROM password_resets WHERE email=%s", (email,))

   
    cursor.execute(
        "INSERT INTO password_resets (email, code, expires_at) VALUES (%s, %s, %s)",
        (email, code, expires_at)
    )
    conn.commit()

    print(f"[DEBUG] Reset code for {email}: {code}")  

    cursor.close()
    conn.close()

    return jsonify({"success": True})

@app.route("/api/verify-code", methods=["POST"])
def verify_code():
    data = request.get_json()
    email = data.get("email")
    code = str(data.get("code")).strip()

    conn = mysql.connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM password_resets WHERE email=%s AND code=%s AND expires_at > NOW()",
        (email, code)
    )

    record = cursor.fetchone()
    cursor.close()
    conn.close()

    if record:
        session["reset_email"] = email
        return jsonify({"success": True})

    return jsonify({"success": False})


@app.route("/api/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()
    password = data.get("password")
    email = session.get("reset_email")

    if not email:
        return jsonify({"success": False, "message": "Session expired"})

    hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")

    conn = mysql.connect()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET password=%s WHERE email=%s",
        (hashed_pw, email)
    )

    cursor.execute(
        "DELETE FROM password_resets WHERE email=%s",
        (email,)
    )

    conn.commit()
    cursor.close()
    conn.close()

    session.pop("reset_email")

    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(debug=True)
