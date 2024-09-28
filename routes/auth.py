from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from datetime import datetime
import re

# Create a blueprint for authentication routes
auth_bp = Blueprint('auth', __name__)

# Connect to MariaDB
def get_db_connection():
    connection = mysql.connector.connect(
        host='35.212.250.168',
        user='yeongchinliong',
        password='qwerty12345',
        database='project_db',
        charset='utf8mb4',  # Force the character set to utf8mb4
        collation='utf8mb4_general_ci'  # Ensure collation is supported
    )
    return connection

# Validation functions (you can keep these here or in a separate utilities file)
def is_valid_sg_address(address):
    """Check if the address contains a 6-digit Singapore postal code."""
    return re.search(r'\b\d{6}\b', address) is not None

def is_valid_sg_phone(phone):
    """Check if the phone number is a valid Singapore number (starts with 6, 8, or 9 and is 8 digits long)."""
    return re.match(r'^[689]\d{7}$', phone) is not None

def is_valid_nric(nric):
    """Check if the NRIC is valid: starts with (S,T,F,G,M), followed by 7 digits and one letter."""
    return re.match(r'^[STFGMstfgm]\d{7}[A-Za-z]$', nric)

# User registration route
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')  # Hash the password
        address = request.form.get('address')  # Optional field
        contact_number = request.form.get('contact_number')  # Optional field
        name = request.form.get('name')  # New field for actual name
        nric = request.form.get('nric')  # New field for NRIC
        gender = request.form.get('gender')  # New field for gender
        dob = request.form.get('dob')  # New field for DOB
        is_staff = 1 if 'is_staff' in request.form else 0
        
        # Validate address and phone number
        if address and not is_valid_sg_address(address):
            flash('Invalid Singapore address. Please provide a valid address with a 6-digit postal code.')
            return redirect(url_for('register'))

        # Validate phone number
        if contact_number and not is_valid_sg_phone(contact_number):
            flash('Invalid Singapore phone number. Please provide a valid 8-digit number starting with 6, 8, or 9.')
            return redirect(url_for('register'))
        
        # Validate NRIC format
        if not is_valid_nric(nric):
            flash('Invalid NRIC format. It must start with S, T, F, G, or M, followed by 7 digits and one letter.')
            return redirect(url_for('register'))

        connection = get_db_connection()
        cursor = connection.cursor()

        # Check if email or nric already exists
        cursor.execute("SELECT * FROM Users WHERE Email = %s", (email,))
        user = cursor.fetchone()
        
        cursor.execute("SELECT * FROM Patients WHERE NRIC = %s", (nric,))
        existing_nric = cursor.fetchone()

        if user:
            flash('Email already registered. Please try a different email.')
            return redirect(url_for('register'))
        
        if existing_nric:
            flash('NRIC already registered. Please try a different NRIC.')
            return redirect(url_for('register'))

        # Insert new user into the database
        cursor.execute("""
            INSERT INTO Users (Username, Email, Password, Address, ContactNumber, IsStaff)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (username, email, hashed_password, address, contact_number, is_staff))
        connection.commit()

        # Get the newly created user's ID
        user_id = cursor.lastrowid

        # Insert a corresponding record into the Patients table with NULL values if the user is not staff
        if not is_staff:
            cursor.execute("""
                INSERT INTO Patients (UserID, PatientName, NRIC, PatientGender, PatientHeight, PatientWeight, PatientDOB, PatientConditions)
                VALUES (%s, %s, %s, %s, NULL, NULL, %s, NULL)
            """, (user_id, name, nric, gender, dob))
            connection.commit()

        cursor.close()
        connection.close()

        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')

# User login route
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect to appropriate dashboard
    if 'username' in session:
        if session.get('is_staff') == 1:
            return redirect(url_for('staff_dashboard'))
        else:
            return redirect(url_for('patient_dashboard'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Server-side validation for empty fields
        if not username or not password:
            flash('Both username and password are required.')
            return redirect(url_for('auth.login'))

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Users WHERE Username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        connection.close()

        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['is_staff'] = user[6]  # IsStaff column

            # Redirect based on whether the user is staff or patient
            if user[6] == 1:  # If IsStaff is 1, it's a staff member
                flash('Welcome, staff member!', 'success')
                return redirect(url_for('staff_dashboard'))
            else:  # If IsStaff is 0, it's a patient
                flash('Welcome, patient!', 'success')
                return redirect(url_for('patient_dashboard'))
        else:
            flash('Invalid login credentials.')
            return redirect(url_for('auth.login'))

    return render_template('login.html')


# User logout route
@auth_bp.route('/logout')
def logout():
    session.clear()  # Clear session data
    return redirect(url_for('auth.login'))

# Route to update the logged-in user's account details
@auth_bp.route('/update_account', methods=['GET', 'POST'])
def update_account():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    connection = get_db_connection()
    cursor = connection.cursor()

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']  # Get the password input
        address = request.form.get('address')
        contact_number = request.form.get('contact_number')
        
        # Validate address and phone number
        if address and not is_valid_sg_address(address):
            flash('Invalid Singapore address. Please provide a valid address with a 6-digit postal code.')
            return redirect(url_for('auth.update_account'))

        if contact_number and not is_valid_sg_phone(contact_number):
            flash('Invalid Singapore phone number. Please provide a valid 8-digit number starting with 6, 8, or 9.')
            return redirect(url_for('auth.update_account'))
        
        # Fetch the existing value of is_staff from the database
        cursor.execute("SELECT IsStaff FROM Users WHERE UserID = %s", (session['user_id'],))
        existing_is_staff = cursor.fetchone()[0]

        # Check if email already exists for another user
        cursor.execute("SELECT * FROM Users WHERE Email = %s AND UserID != %s", (email, session['user_id']))
        existing_user = cursor.fetchone()

        if existing_user:
            flash('Email is already in use by another account.')
            return redirect(url_for('auth.update_account'))

        # Fetch the existing hashed password from the database
        cursor.execute("SELECT Password FROM Users WHERE UserID = %s", (session['user_id'],))
        existing_hashed_password = cursor.fetchone()[0]

        # Only re-hash and update the password if a new one is provided
        if password.strip():  # Check if a new password is entered
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        else:
            # If no new password is provided, keep the old hashed password
            hashed_password = existing_hashed_password

        # Update user details in the database
        cursor.execute("""
            UPDATE Users
            SET Username = %s, Email = %s, Password = %s, Address = %s, ContactNumber = %s, IsStaff = %s
            WHERE UserID = %s
        """, (username, email, hashed_password, address, contact_number, existing_is_staff, session['user_id']))
        connection.commit()

        # Update session data with new username
        session['username'] = username
        flash('Account updated successfully!', 'success')
        return redirect(url_for('auth.update_account'))

    # Fetch the current user's data (join Users and Patients tables)
    cursor.execute("""
        SELECT u.Username, u.Email, u.Password, u.Address, u.ContactNumber, p.PatientName, p.NRIC, p.PatientGender, p.PatientDOB
        FROM Users u
        LEFT JOIN Patients p ON u.UserID = p.UserID
        WHERE u.UserID = %s
    """, (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()
    connection.close()

    return render_template('update_account.html', user=user)

# Route to delete the user's account
@auth_bp.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    connection = get_db_connection()
    cursor = connection.cursor()

    # Delete the user's account from the database
    cursor.execute("DELETE FROM Users WHERE UserID = %s", (session['user_id'],))
    connection.commit()
    cursor.close()
    connection.close()

    # Clear session and log the user out after account deletion
    session.clear()
    flash('Your account has been deleted successfully.', 'success')
    return redirect(url_for('auth.register'))