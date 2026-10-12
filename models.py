"""
Database models for the Budget Manager web app.

This file defines the structure (schema) of all database tables using SQLAlchemy.
Each class below represents one table in the database. SQLAlchemy converts these
Python classes into SQL CREATE TABLE statements behind the scenes.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

# This is the SQLAlchemy database object. It gets connected to the Flask app
# in app.py via db.init_app(app). All models use this object to define columns.
db = SQLAlchemy()


class User(UserMixin, db.Model):
    """
    Represents a registered user in the application.

    UserMixin is from Flask-Login and provides default implementations for
    things like is_authenticated, is_active, get_id() — methods that
    Flask-Login needs to manage user sessions. Without it, we'd have to
    write those methods ourselves.

    db.Model tells SQLAlchemy that this class maps to a database table.
    The table name is automatically set to "user" (lowercase class name).
    """
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    # Stores a hashed version of the password, never the plain text.
    password_hash = db.Column(db.String(256), nullable=False)
    # One user can have many budgets. "cascade=all, delete-orphan" means
    # if a user is deleted, all their budgets are automatically deleted too.
    budgets = db.relationship("MonthlyBudget", backref="user", cascade="all, delete-orphan")


class MonthlyBudget(db.Model):
    """
    Represents a budget for a specific month and year, owned by one user.

    This is the same as the monthly_budget table from the iPhone app,
    but with an added user_id column to track which user owns the budget.
    """
    id = db.Column(db.Integer, primary_key=True)
    # Links this budget to a specific user. db.ForeignKey means this column
    # references the "id" column in the "user" table.
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    # One budget can have many transactions.
    transactions = db.relationship("Transaction", backref="budget", cascade="all, delete-orphan")

    # Ensures one user can only have one budget per month.
    # Same as UNIQUE(user_id, year, month) in raw SQL.
    __table_args__ = (db.UniqueConstraint("user_id", "year", "month"),)


class Transaction(db.Model):
    """
    Represents a single expense or extra cash entry within a monthly budget.

    Negative amounts are expenses, positive amounts are extra cash received.
    This is the same as the transactions table from the iPhone app.
    """
    id = db.Column(db.Integer, primary_key=True)
    # Links this transaction to a specific budget.
    budget_id = db.Column(db.Integer, db.ForeignKey("monthly_budget.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    # default=datetime.now means if no date is provided, it uses the current time.
    date = db.Column(db.DateTime, nullable=False, default=datetime.now)
