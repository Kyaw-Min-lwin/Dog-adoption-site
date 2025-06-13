from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
import MySQLdb.cursors
import os
import re
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "zt64nC1VVk"

# mysql configuration
app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = "idkSth1*"
app.config["MYSQL_DB"] = "pawportal_db"

mysql = MySQL(app)

UPLOAD_FOLDER = "./static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# Routes
@app.route("/")
def home():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM pets WHERE status='Available'")
    pets = cursor.fetchall()
    return render_template("index.html", pets=pets)


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
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("home"))
        else:
            flash("Incorrect email or password!", "danger")
    return render_template("login.html")


@app.route("/register/", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm = request.form.get("confirm")

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        account = cursor.fetchone()

        if account:
            flash("Email already registered!", "warning")
        elif not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash("Invalid email address!", "danger")
        elif password != confirm:
            flash("Passwords do not match!", "danger")
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
    if "loggedin" in session:
        session.clear()
        flash("You have been logged out.", "info")
        return redirect(url_for("login"))
    else:
        flash("You are not logged in.", "warning")
        return redirect(url_for("login"))


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/adopt/<int:pet_id>")
def adopt(pet_id):
    if "loggedin" in session:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Check if the pet exists and is available
        cursor.execute("SELECT * FROM pets WHERE id = %s", (pet_id,))
        pet = cursor.fetchone()

        if pet and pet["status"] == "Available":
            user_id = session["id"]

            # Check if the user already made a request for this pet (optional but recommended)
            cursor.execute(
                "SELECT * FROM adoption_requests WHERE user_id = %s AND pet_id = %s",
                (user_id, pet_id),
            )
            existing_request = cursor.fetchone()

            if existing_request:
                flash(f"You have already requested to adopt {pet['name']}.", "info")
            else:
                # Insert new adoption request with status 'Pending'
                cursor.execute(
                    "INSERT INTO adoption_requests (user_id, pet_id, status) VALUES (%s, %s, %s)",
                    (user_id, pet_id, "Pending"),
                )
                mysql.connection.commit()
                flash(
                    f"Your adoption request for {pet['name']} has been submitted!",
                    "success",
                )
        else:
            flash("This pet is not available for adoption.", "warning")

        return redirect(url_for("home"))

    else:
        flash("You must be logged in to adopt a pet.", "danger")
        return redirect(url_for("login"))


@app.route("/admin/dashboard")
def admin_dashboard():
    if "loggedin" not in session or session.get("role") != "admin":
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM pets")
    total_pets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM pets WHERE status = 'Available'")
    available_pets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM adoption_requests WHERE status = 'Pending'")
    pending_requests = cursor.fetchone()[0]

    return render_template(
        "admin/dashboard.html",
        total_pets=total_pets,
        available_pets=available_pets,
        pending_requests=pending_requests,
    )


@app.route("/admin/pets")
def admin_manage_pets():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(
        """
        SELECT pets.*, breeds.name AS breed_name, species.name AS species_name
        FROM pets
        JOIN breeds ON pets.breed_id = breeds.id
        JOIN species ON pets.species_id = species.id
    """
    )
    pets = cursor.fetchall()
    unique_species = list({(pet["species_id"], pet["species_name"]) for pet in pets})
    cursor.execute("SELECT * FROM breeds")
    breeds = cursor.fetchall()
    return render_template(
        "admin/manage_pets.html",
        pets=pets,
        species_list=unique_species,
        breed_list=breeds,
    )


@app.route("/admin/pets/edit/<int:pet_id>", methods=["POST"])
def admin_edit_pet(pet_id):
    if "loggedin" not in session or session.get("role") != "admin":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("login"))

    name = request.form["name"]
    description = request.form["description"]
    age = request.form["age"]
    status = request.form["status"]

    # Handle image file
    if "image_file" not in request.files:
        flash("No image uploaded.", "danger")
        return redirect(url_for("admin_manage_pets"))

    image = request.files["image_file"]
    if image.filename == "" or not allowed_file(image.filename):
        flash("Invalid image file.", "danger")
        return redirect(url_for("admin_manage_pets"))
    filename = secure_filename(image.filename)
    image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    image.save(image_path)

    # Save relative path to DB (e.g., /static/uploads/dog1.jpg)
    image_url = f"/{image_path}"

    try:
        cursor = mysql.connection.cursor()
        cursor.execute(
            """
            UPDATE pets
            SET name = %s, description = %s, image_url = %s, age= %s ,status = %s
            WHERE id = %s
        """,
            (name, description, image_url, age, status, pet_id),
        )
        mysql.connection.commit()
        cursor.close()

        flash(f'Pet "{name}" updated successfully!', "success")
        return redirect(url_for("admin_manage_pets"))
    except Exception as e:
        flash(f"An error occurred while updating the pet: {str(e)}", "danger")
        return redirect(url_for("admin_manage_pets"))
    finally:
        cursor.close()


@app.route("/admin/pets/delete/<int:pet_id>")
def admin_delete_pet(pet_id):
    if "loggedin" not in session or session.get("role") != "admin":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM pets WHERE id = %s", (pet_id,))
    mysql.connection.commit()
    cursor.close()

    flash("Pet deleted successfully!", "success")
    return redirect(url_for("admin_manage_pets"))


@app.route("/admin/pets/add", methods=["POST"])
def admin_add_pet():
    if "loggedin" not in session or session.get("role") != "admin":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("login"))

    name = request.form["name"]
    description = request.form["description"]
    breed_id = request.form["breed_id"]
    species_id = request.form["species_id"]
    status = request.form["status"]
    # Handle image file
    if "image_file" not in request.files:
        flash("No image uploaded.", "danger")
        return redirect(url_for("admin_manage_pets"))

    image = request.files["image_file"]
    if image.filename == "" or not allowed_file(image.filename):
        flash("Invalid image file.", "danger")
        return redirect(url_for("admin_manage_pets"))
    filename = secure_filename(image.filename)
    image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    image.save(image_path)

    # Save relative path to DB (e.g., /static/uploads/dog1.jpg)
    image_url = f"/{image_path}"

    # Check that breed_id belongs to the selected species_id
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT species_id FROM breeds WHERE id = %s", (breed_id,))
    result = cursor.fetchone()

    if result and str(result["species_id"]) != species_id:
        flash("Selected breed does not belong to the selected species.", "danger")
        return redirect(url_for("admin_manage_pets"))

    # Proceed with valid data
    cursor.execute(
        """
        INSERT INTO pets (name, description, image_url, breed_id, species_id, status)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (name, description, image_url, breed_id, species_id, status),
    )
    mysql.connection.commit()
    cursor.close()

    flash(f'Pet "{name}" added successfully!', "success")
    return redirect(url_for("admin_manage_pets"))


@app.route("/admin/adoption_requests")
def admin_manage_adoptions():
    return render_template("admin/manage_adoptions.html")


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template("500.html"), 500


@app.route("/volunteer", methods=["GET", "POST"])
def volunteer():
    if request.method == "POST":
        if "loggedin" in session:
            # Get form data
            first_name = request.form.get("first_name")
            last_name = request.form.get("last_name")
            email = request.form.get("email")
            phone = request.form.get("phone")

            # Basic validation
            if not all([first_name, last_name, email, phone]):
                flash("All fields are required.", "danger")
                return redirect(url_for("volunteer"))

            # email format validation
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                flash("Invalid email address.", "danger")
                return redirect(url_for("volunteer"))

            # phone number format validation (basic check)
            if not re.match(r"^\+?[1-9]\d{1,14}$", phone):
                flash("Invalid phone number.", "danger")
                return redirect(url_for("volunteer"))
            cursor = mysql.connection.cursor()
            cursor.execute(
                "INSERT INTO volunteers (first_name, last_name, email, phone) VALUES (%s, %s, %s, %s)",
                (first_name, last_name, email, phone),
            )
            mysql.connection.commit()
            cursor.close()

            flash("Thank you for signing up as a volunteer!", "success")
            return redirect(url_for("volunteer"))
        else:
            flash("You must be logged in to volunteer", "warning")
            return redirect(url_for("login"))

    return render_template("volunteer.html")


if __name__ == "__main__":
    app.run(debug=True)
