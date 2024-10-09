# routes/auth.py

from flask import render_template, request, redirect, session, url_for, flash
from . import auth_bp
from db import get_db_connection
from utils import is_valid_nric, is_valid_sg_address, is_valid_sg_phone
from werkzeug.security import generate_password_hash, check_password_hash

# User login route
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Display the correct dashboard based on role
    if 'username' in session:
        if session.get('is_staff') == 1:
            return redirect(url_for('staff.staff_dashboard'))
        else:
            return redirect(url_for('patient.patient_dashboard'))
        
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
            session['is_staff'] = user[6]

            # Redirect based on whether the user is staff or patient
            if user[6] == 1: 
                flash('Welcome, staff member!', 'success')
                return redirect(url_for('staff.staff_dashboard'))
            else:  
                flash('Welcome, patient!', 'success')
                return redirect(url_for('patient.patient_dashboard'))
        else:
            flash('Invalid login credentials.')
            return redirect(url_for('auth.login'))

    return render_template('login.html')


# User registration route
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')  # Hash the password
        address = request.form.get('address')
        contact_number = request.form.get('contact_number')
        name = request.form.get('name')
        nric = request.form.get('nric')
        gender = request.form.get('gender')
        dob = request.form.get('dob')
        is_staff = 1 if 'is_staff' in request.form else 0
        
        # Validate address
        if address and not is_valid_sg_address(address):
            flash('Invalid Singapore address. Please provide a valid address with a 6-digit postal code.')
            return redirect(url_for('auth.register'))

        # Validate phone number
        if contact_number and not is_valid_sg_phone(contact_number):
            flash('Invalid Singapore phone number. Please provide a valid 8-digit number starting with 6, 8, or 9.')
            return redirect(url_for('auth.register'))
        
        # Validate NRIC format
        if not is_valid_nric(nric):
            flash('Invalid NRIC format. It must start with S, T, F, G, or M, followed by 7 digits and one letter.')
            return redirect(url_for('auth.register'))

        connection = get_db_connection()
        cursor = connection.cursor()

        # Check if email or nric already exists
        cursor.execute("SELECT * FROM Users WHERE Email = %s", (email,))
        user = cursor.fetchone()
        
        cursor.execute("SELECT * FROM Patients WHERE NRIC = %s", (nric,))
        existing_nric = cursor.fetchone()

        if user:
            flash('Email already registered. Please try a different email.')
            return redirect(url_for('auth.register'))
        
        if existing_nric:
            flash('NRIC already registered. Please try a different NRIC.')
            return redirect(url_for('auth.register'))

        # Insert new user into the database
        cursor.execute("""
            INSERT INTO Users (Username, Email, Password, Address, ContactNumber, IsStaff)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (username, email, hashed_password, address, contact_number, is_staff))
        connection.commit()

        # Get the newly created user's ID
        user_id = cursor.lastrowid

        # Insert a corresponding record into the Patients table with NULL values for height and weight
        if not is_staff:
            cursor.execute("""
                INSERT INTO Patients (UserID, PatientName, NRIC, PatientGender, PatientHeight, PatientWeight, PatientDOB)
                VALUES (%s, %s, %s, %s, NULL, NULL, %s)
            """, (user_id, name, nric, gender, dob))
            connection.commit()

        cursor.close()
        connection.close()

        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')

# User logout route
@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

# Delete user route, only for staff member
@auth_bp.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    connection = get_db_connection()
    cursor = connection.cursor()
    
    # Delete all records associated with the user/patient
    cursor.execute("DELETE FROM Prescriptions WHERE PatientID = (SELECT PatientID FROM Patients WHERE UserID = %s)", (session['user_id'],))
    cursor.execute("DELETE FROM PatientHistory WHERE PatientID = (SELECT PatientID FROM Patients WHERE UserID = %s)", (session['user_id'],))
    cursor.execute("DELETE FROM Appointments WHERE PatientID = (SELECT PatientID FROM Patients WHERE UserID = %s)", (session['user_id'],))
    cursor.execute("DELETE FROM Patients WHERE UserID = %s", (session['user_id'],))
    cursor.execute("DELETE FROM Users WHERE UserID = %s", (session['user_id'],))
    connection.commit()
    cursor.close()
    connection.close()

    # Clear session and log the user out after deleting account
    session.clear()
    flash('Your account has been deleted successfully.', 'success')
    return redirect(url_for('auth.register'))