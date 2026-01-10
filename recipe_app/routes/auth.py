from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import mysql

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")

@auth_bp.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        username = request.form["username"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])
        cur = mysql.connection.cursor()
        try:
            cur.execute("INSERT INTO users (username,email,password) VALUES (%s,%s,%s)", (username,email,password))
            mysql.connection.commit()
            flash("Registration successful! Login now.","success")
            return redirect(url_for("auth.login"))
        except:
            flash("User exists or error!","danger")
            return redirect(url_for("auth.register"))
        finally:
            cur.close()
    return render_template("register.html")

@auth_bp.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email = request.form["email"]
        password = request.form["password"]
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s",(email,))
        user = cur.fetchone()
        cur.close()
        if user and check_password_hash(user[3],password):
            session["user_id"]=user[0]
            session["username"]=user[1]
            flash("Login successful","success")
            return redirect(url_for("recipes.dashboard_recipes"))
        else:
            flash("Invalid credentials","danger")
            return redirect(url_for("auth.login"))
    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully","success")
    return redirect(url_for("auth.login"))
