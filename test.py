from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from flask_login import login_required
import MySQLdb.cursors
import re
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "zt64nC1VVk"

# mysql configuration
app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = "idkSth1*"
app.config["MYSQL_DB"] = "pawportal_db"

mysql = MySQL(app)


# Routes
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute(f"SELECT * FROM users WHERE email = %s ", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user["password"], password):
            session["loggedin"] = True
            session["id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            flash("Logged in successfully!", "success")
            return redirect(url_for("home"))
        else:
            flash("Incorrect email or password!", "danger")
    return render_template("login.html")


@app.route("/register/", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form["email"]
        password = request.form["password"]

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        account = cursor.fetchone()

        if account:
            flash("Email already registered!", "warning")
        elif not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash("Invalid email address!", "danger")
        else:
            hashed_password = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                (name, email, hashed_password),
            )
            mysql.connection.commit()
            flash("You are now registered!", "success")
            return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/admin/")
@login_required
def admin():
    return render_template("admin.html")


if __name__ == "__main__":
    app.run(debug=True)
