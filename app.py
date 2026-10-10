import os
import calendar
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, MonthlyBudget, Transaction

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///budget.db")

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        if not username or not password:
            flash("Username and password are required.")
            return redirect(url_for("register"))
        if User.query.filter_by(username=username).first():
            flash("Username already taken.")
            return redirect(url_for("register"))
        user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.")
        return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/")
@app.route("/dashboard")
@app.route("/dashboard/<int:year>/<int:month>")
@login_required
def dashboard(year=None, month=None):
    if year is None or month is None:
        year = datetime.now().year
        month = datetime.now().month

    budget = MonthlyBudget.query.filter_by(
        user_id=current_user.id, year=year, month=month
    ).first()

    transactions = []
    remaining = 0
    budget_amount = 0
    used_percentage = 0

    if budget:
        budget_amount = budget.amount
        transactions = Transaction.query.filter_by(budget_id=budget.id).order_by(Transaction.date.desc()).all()
        total_spent = sum(t.amount for t in transactions)
        remaining = budget.amount + total_spent
        used_percentage = 1 - (remaining / budget.amount) if budget.amount > 0 else 0

    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

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


@app.route("/set_budget", methods=["POST"])
@login_required
def set_budget():
    year = int(request.form["year"])
    month = int(request.form["month"])
    amount = float(request.form["amount"])
    if amount <= 0:
        return redirect(url_for("dashboard", year=year, month=month))

    budget = MonthlyBudget.query.filter_by(
        user_id=current_user.id, year=year, month=month
    ).first()
    if budget:
        budget.amount = amount
    else:
        budget = MonthlyBudget(user_id=current_user.id, year=year, month=month, amount=amount)
        db.session.add(budget)
    db.session.commit()
    return redirect(url_for("dashboard", year=year, month=month))


@app.route("/add_transaction", methods=["POST"])
@login_required
def add_transaction():
    year = int(request.form["year"])
    month = int(request.form["month"])
    amount = float(request.form["amount"])
    tx_type = request.form["type"]

    budget = MonthlyBudget.query.filter_by(
        user_id=current_user.id, year=year, month=month
    ).first()
    if not budget or amount <= 0:
        return redirect(url_for("dashboard", year=year, month=month))

    if tx_type == "expense":
        amount = -amount

    transaction = Transaction(budget_id=budget.id, amount=amount)
    db.session.add(transaction)
    db.session.commit()
    return redirect(url_for("dashboard", year=year, month=month))


@app.route("/delete_transaction/<int:transaction_id>", methods=["POST"])
@login_required
def delete_transaction(transaction_id):
    transaction = db.session.get(Transaction, transaction_id)
    if transaction and transaction.budget.user_id == current_user.id:
        year = transaction.budget.year
        month = transaction.budget.month
        db.session.delete(transaction)
        db.session.commit()
        return redirect(url_for("dashboard", year=year, month=month))
    return redirect(url_for("dashboard"))


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
