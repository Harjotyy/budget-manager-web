"""
Budget Manager Web Application

This is the main file that runs the web app. It handles:
- Creating the Flask app and connecting it to the database
- User registration, login, and logout
- The budget dashboard (viewing/setting budgets, adding/deleting transactions)

Every function with @app.route is a "route" — it tells Flask which function
to run when a user visits a specific URL in their browser.
"""

import os
import calendar
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, MonthlyBudget, Transaction

# --- App Setup ---

# Create the Flask application.
app = Flask(__name__)

# SECRET_KEY is used by Flask to encrypt session cookies (keeps users logged in).
# In production, this is set as an environment variable on the server.
# Locally, it falls back to a dev default.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

# DATABASE_URL tells SQLAlchemy where to find the database.
# Locally: uses SQLite (a file called budget.db, just like the iPhone app).
# On Render: this will be set to a PostgreSQL URL.
# Render gives postgres:// but SQLAlchemy requires postgresql://
database_url = os.environ.get("DATABASE_URL", "sqlite:///budget.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url

# Connect the database (defined in models.py) to this Flask app.
db.init_app(app)

# Set up Flask-Login to handle user sessions.
login_manager = LoginManager(app)
# If a user who isn't logged in tries to visit a protected page,
# Flask-Login will redirect them to the "login" route.
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    """
    Called automatically by Flask-Login on every request.

    When a user logs in, their user_id is stored in a browser cookie.
    On every subsequent request, Flask-Login calls this function to load
    the full User object from the database using that stored ID.
    This is how the app knows who is making each request.
    """
    return db.session.get(User, int(user_id))


# --- Authentication Routes ---


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Handles user registration.

    GET request (user visits /register):
        Shows the registration form.

    POST request (user submits the form):
        Reads the username and password from the form, validates them,
        creates a new user in the database with a hashed password,
        logs them in, and redirects to the dashboard.
    """
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if not username or not password:
            flash("Username and password are required.")
            return redirect(url_for("register"))

        # Check if someone already registered with this username.
        if User.query.filter_by(username=username).first():
            flash("Username already taken.")
            return redirect(url_for("register"))

        # generate_password_hash turns "abc123" into something like
        # "pbkdf2:sha256:260000$xQ..." that cannot be reversed.
        # We never store the actual password.
        user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()

        # Automatically log the user in after registration.
        login_user(user)
        return redirect(url_for("dashboard"))

    # If it's a GET request, just show the registration page.
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Handles user login.

    GET request (user visits /login):
        Shows the login form.

    POST request (user submits the form):
        Looks up the user by username, checks if the password matches
        the stored hash, and if so, logs them in and redirects to
        the dashboard.
    """
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        # Look up the user by username.
        user = User.query.filter_by(username=username).first()

        # check_password_hash compares the entered password against the
        # stored hash. It returns True if they match, False otherwise.
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    """
    Logs the user out and redirects them to the login page.

    @login_required means only logged-in users can access this route.
    If someone who isn't logged in visits /logout, they get redirected
    to the login page instead.
    """
    logout_user()
    return redirect(url_for("login"))


# --- Dashboard Route ---


@app.route("/")
@app.route("/dashboard")
@app.route("/dashboard/<int:year>/<int:month>")
@login_required
def dashboard(year=None, month=None):
    """
    Shows the main budget dashboard for a specific month.

    This route has three URL patterns:
    - /              → shows the current month
    - /dashboard     → shows the current month
    - /dashboard/2026/10  → shows October 2026

    This is the web equivalent of the refresh_data() method in the iPhone app.
    It loads the budget and transactions for the selected month, calculates
    how much money is left, and sends all that data to the dashboard.html
    template to be displayed.
    """
    # If no year/month specified in the URL, default to the current month.
    if year is None or month is None:
        year = datetime.now().year
        month = datetime.now().month

    # Look up this user's budget for the selected month.
    # current_user is provided by Flask-Login — it's the logged-in user.
    budget = MonthlyBudget.query.filter_by(
        user_id=current_user.id, year=year, month=month
    ).first()

    # Set default values in case there's no budget yet.
    transactions = []
    remaining = 0
    budget_amount = 0
    used_percentage = 0

    if budget:
        budget_amount = budget.amount
        # Get all transactions for this budget, newest first.
        transactions = Transaction.query.filter_by(
            budget_id=budget.id
        ).order_by(Transaction.date.desc()).all()
        # Calculate remaining budget (same logic as the iPhone app).
        total_spent = sum(t.amount for t in transactions)
        remaining = budget.amount + total_spent
        used_percentage = 1 - (remaining / budget.amount) if budget.amount > 0 else 0

    # Calculate previous and next month for the navigation arrows.
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    # Send all the data to the HTML template. The template uses these
    # variables to display the budget, transactions, colors, etc.
    return render_template(
        "dashboard.html",
        year=year,
        month=month,
        month_name=calendar.month_name[month],
        budget=budget,
        budget_amount=budget_amount,
        remaining=remaining,
        used_percentage=used_percentage,
        transactions=transactions,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
    )


# --- Action Routes ---
# These routes handle form submissions (POST only). They don't show pages —
# they process data and redirect back to the dashboard.


@app.route("/set_budget", methods=["POST"])
@login_required
def set_budget():
    """
    Sets or updates the budget for a specific month.

    Called when the user submits the "Set Budget" form on the dashboard.
    If a budget already exists for that month, it updates the amount.
    If not, it creates a new one.

    This is the web equivalent of on_set_budget() in the iPhone app.
    """
    year = int(request.form["year"])
    month = int(request.form["month"])
    amount = float(request.form["amount"])

    if amount <= 0:
        return redirect(url_for("dashboard", year=year, month=month))

    # Check if a budget already exists for this user/month.
    budget = MonthlyBudget.query.filter_by(
        user_id=current_user.id, year=year, month=month
    ).first()

    if budget:
        # Budget exists — just update the amount.
        budget.amount = amount
    else:
        # No budget yet — create a new one.
        budget = MonthlyBudget(user_id=current_user.id, year=year, month=month, amount=amount)
        db.session.add(budget)

    db.session.commit()
    return redirect(url_for("dashboard", year=year, month=month))


@app.route("/add_transaction", methods=["POST"])
@login_required
def add_transaction():
    """
    Adds an expense or extra cash transaction to the current month's budget.

    The form sends a "type" field that is either "expense" or "cash".
    Expenses are stored as negative amounts, extra cash as positive.

    This is the web equivalent of on_add_expense() and on_add_cash()
    in the iPhone app, combined into one route.
    """
    year = int(request.form["year"])
    month = int(request.form["month"])
    amount = float(request.form["amount"])
    tx_type = request.form["type"]

    # Look up the budget to attach this transaction to.
    budget = MonthlyBudget.query.filter_by(
        user_id=current_user.id, year=year, month=month
    ).first()

    if not budget or amount <= 0:
        return redirect(url_for("dashboard", year=year, month=month))

    # Expenses are stored as negative numbers, same as the iPhone app.
    if tx_type == "expense":
        amount = -amount

    transaction = Transaction(budget_id=budget.id, amount=amount)
    db.session.add(transaction)
    db.session.commit()
    return redirect(url_for("dashboard", year=year, month=month))


@app.route("/delete_transaction/<int:transaction_id>", methods=["POST"])
@login_required
def delete_transaction(transaction_id):
    """
    Deletes a transaction by its ID.

    The <int:transaction_id> in the URL pattern means Flask extracts the
    number from the URL and passes it as a parameter. For example,
    /delete_transaction/42 would pass transaction_id=42.

    Before deleting, it checks that the transaction belongs to the
    logged-in user (so users can't delete each other's transactions).

    This is the web equivalent of on_delete_transaction() in the iPhone app.
    """
    transaction = db.session.get(Transaction, transaction_id)

    # Verify the transaction exists AND belongs to the current user.
    if transaction and transaction.budget.user_id == current_user.id:
        year = transaction.budget.year
        month = transaction.budget.month
        db.session.delete(transaction)
        db.session.commit()
        return redirect(url_for("dashboard", year=year, month=month))

    return redirect(url_for("dashboard"))


# --- Database Initialization ---

# Create all database tables when the app starts (if they don't exist yet).
# This is equivalent to init_db() in the iPhone app's db.py.
with app.app_context():
    db.create_all()


if __name__ == "__main__":
    # Starts the Flask development server on http://127.0.0.1:5000.
    # debug=True means the server auto-reloads when you change code
    # and shows detailed error pages.
    app.run(debug=True)
