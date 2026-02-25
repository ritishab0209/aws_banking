import os
import time
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

# -------------------- MYSQL CONFIG --------------------

DB_USER = os.environ.get("MYSQL_USER")
DB_PASSWORD = os.environ.get("MYSQL_PASSWORD")
DB_HOST = os.environ.get("MYSQL_HOST")
DB_NAME = os.environ.get("MYSQL_DATABASE")

app.config['SQLALCHEMY_DATABASE_URI'] = \
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# -------------------- MODELS --------------------

class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    accounts = db.relationship(
        'Account',
        backref='customer',
        lazy=True,
        cascade="all, delete"
    )


class Account(db.Model):
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(20), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)

    customer_id = db.Column(
        db.Integer,
        db.ForeignKey('customers.id'),
        nullable=False
    )

    transactions = db.relationship(
        'Transaction',
        backref='account',
        lazy=True,
        cascade="all, delete"
    )


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20))
    amount = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    account_id = db.Column(
        db.Integer,
        db.ForeignKey('accounts.id'),
        nullable=False
    )


# -------------------- WAIT FOR DATABASE --------------------

def wait_for_db():
    retries = 10
    while retries > 0:
        try:
            db.create_all()
            print("✅ Database connected and tables created")
            return
        except OperationalError:
            print("⏳ Waiting for MySQL to start...")
            retries -= 1
            time.sleep(5)

    print("❌ Could not connect to MySQL after multiple attempts")
    exit(1)


with app.app_context():
    wait_for_db()


# -------------------- ROUTES --------------------

@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        if Customer.query.filter_by(email=email).first():
            flash("Email already registered")
            return redirect(url_for('register'))

        new_customer = Customer(name=name, email=email, password=password)
        db.session.add(new_customer)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        customer = Customer.query.filter_by(email=email).first()

        if customer and check_password_hash(customer.password, password):
            session['customer_id'] = customer.id
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials")
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'customer_id' not in session:
        return redirect(url_for('login'))

    customer = Customer.query.get(session['customer_id'])
    return render_template('dashboard.html', customer=customer)


@app.route('/create_account', methods=['POST'])
def create_account():
    if 'customer_id' not in session:
        return redirect(url_for('login'))

    account_number = request.form['account_number']

    new_account = Account(
        account_number=account_number,
        customer_id=session['customer_id']
    )

    db.session.add(new_account)
    db.session.commit()

    return redirect(url_for('dashboard'))


@app.route('/deposit/<int:account_id>', methods=['POST'])
def deposit(account_id):
    account = Account.query.get(account_id)
    amount = float(request.form['amount'])

    account.balance += amount

    transaction = Transaction(
        type="Deposit",
        amount=amount,
        account_id=account.id
    )

    db.session.add(transaction)
    db.session.commit()

    return redirect(url_for('dashboard'))


@app.route('/withdraw/<int:account_id>', methods=['POST'])
def withdraw(account_id):
    account = Account.query.get(account_id)
    amount = float(request.form['amount'])

    if account.balance >= amount:
        account.balance -= amount

        transaction = Transaction(
            type="Withdrawal",
            amount=amount,
            account_id=account.id
        )

        db.session.add(transaction)
        db.session.commit()

    return redirect(url_for('dashboard'))


@app.route('/delete_account/<int:id>')
def delete_account(id):
    account = Account.query.get(id)
    db.session.delete(account)
    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# -------------------- RUN APP --------------------

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
