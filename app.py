from flask import Flask, render_template, request, redirect, session, url_for, flash
import re
import mysql.connector
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure key

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

# Validation functions
def is_valid_sg_address(address):
    """Check if the address contains a 6-digit Singapore postal code."""
    # Check if there's a 6-digit number anywhere in the address
    return re.search(r'\b\d{6}\b', address) is not None

def is_valid_sg_phone(phone):
    """Check if the phone number is a valid Singapore number (starts with 6, 8, or 9 and is 8 digits long)."""
    return re.match(r'^[689]\d{7}$', phone) is not None

@app.route('/')
def index():
    return redirect('login')

# User registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
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

        if contact_number and not is_valid_sg_phone(contact_number):
            flash('Invalid Singapore phone number. Please provide a valid 8-digit number starting with 6, 8, or 9.')
            return redirect(url_for('register'))

        connection = get_db_connection()
        cursor = connection.cursor()

        # Check if email already exists
        cursor.execute("SELECT * FROM Users WHERE Email = %s", (email,))
        user = cursor.fetchone()

        if user:
            flash('Email already registered. Please try a different email.')
            return redirect(url_for('register'))

        # Insert new user into the database
        cursor.execute("""
            INSERT INTO Users (Username, Email, Password, Address, ContactNumber, IsStaff)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (username, email, password, address, contact_number, is_staff))
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
        return redirect(url_for('login'))

    return render_template('register.html')

# User login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Server-side validation for empty fields
        if not username or not password:
            flash('Both username and password are required.')
            return redirect(url_for('login'))

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Users WHERE Username = %s AND Password = %s", (username, password))
        user = cursor.fetchone()
        cursor.close()
        connection.close()

        if user:
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
            return redirect(url_for('login'))

    return render_template('login.html')

# edit patient records
@app.route('/edit_patient/<int:patient_id>', methods=['GET', 'POST'])
def edit_patient(patient_id):
    if 'is_staff' not in session or session['is_staff'] != 1:
        flash('You do not have access to this page.')
        return redirect(url_for('login'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == 'POST':
        patient_name = request.form['patient_name']
        nric = request.form['nric']  # New NRIC field
        patient_gender = request.form['patient_gender']
        patient_height = request.form['patient_height']
        patient_weight = request.form['patient_weight']
        patient_dob = request.form['patient_dob']
        patient_conditions = request.form['patient_conditions']

        try:
            cursor.execute("""
                UPDATE Patients
                SET PatientName = %s, NRIC = %s, PatientGender = %s, PatientHeight = %s, 
                    PatientWeight = %s, PatientDOB = %s, PatientConditions = %s
                WHERE UserID = %s
            """, (patient_name, nric, patient_gender, patient_height, patient_weight,
                  patient_dob, patient_conditions, patient_id))
            connection.commit()
            flash('Patient details updated successfully!', 'success')
        except mysql.connector.Error as err:
            flash(f'An error occurred: {err}', 'danger')

        return redirect(url_for('staff_dashboard'))

    # Fetch patient details
    cursor.execute("SELECT * FROM Patients WHERE UserID = %s", (patient_id,))
    patient = cursor.fetchone()

    cursor.close()
    connection.close()

    if patient:
        return render_template('edit_patient.html', patient=patient)
    else:
        flash('Patient not found.', 'danger')
        return redirect(url_for('staff_dashboard'))


@app.route('/book_appointment', methods=['GET', 'POST'])
def book_appointment():
    if 'user_id' not in session:
        flash('Please log in to book an appointment.')
        return redirect(url_for('login'))

    if session.get('is_staff') == 1:
        flash('Staff members cannot book appointments.')
        return redirect(url_for('staff_dashboard'))

    if request.method == 'POST':
        # Collect form data
        appt_date = request.form.get('appt_date')
        appt_time = request.form.get('appt_time')
        appt_reason = request.form.get('appt_reason')

        # Basic validation
        if not appt_date or not appt_time or not appt_reason:
            flash('All fields are required.')
            return redirect(url_for('book_appointment'))

        # Validate date and time formats
        try:
            appt_date_obj = datetime.strptime(appt_date, '%Y-%m-%d').date()
            appt_time_obj = datetime.strptime(appt_time, '%H:%M').time()
        except ValueError:
            flash('Invalid date or time format.')
            return redirect(url_for('book_appointment'))

        # Optional: Add more validations, e.g., appointment in the future
        if appt_date_obj < datetime.today().date():
            flash('Appointment date must be in the future.')
            return redirect(url_for('book_appointment'))

        # Connect to the database
        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            # Fetch PatientID for the current user
            cursor.execute("SELECT PatientID FROM Patients WHERE UserID = %s", (session['user_id'],))
            patient = cursor.fetchone()

            if not patient:
                flash('Patient record not found. Please contact support.')
                return redirect(url_for('patient_dashboard'))

            patient_id = patient[0]

            # Insert the appointment into the Appointments table
            cursor.execute("""
                INSERT INTO Appointments (PatientID, ApptDate, ApptTime, ApptStatus, ApptReason)
                VALUES (%s, %s, %s, %s, %s)
            """, (patient_id, appt_date_obj, appt_time_obj, 'Pending', appt_reason))
            connection.commit()

            flash('Appointment booked successfully!', 'success')
            return redirect(url_for('patient_dashboard'))

        except mysql.connector.Error as err:
            print(f"Error: {err}")
            flash('An error occurred while booking the appointment. Please try again.', 'danger')
            return redirect(url_for('book_appointment'))

        finally:
            cursor.close()
            connection.close()

    return render_template('book_appointment.html')

# User logout route
@app.route('/logout')
def logout():
    session.clear()  # Clear session data
    return redirect(url_for('login'))

# Route to update the logged-in user's account details
@app.route('/update_account', methods=['GET', 'POST'])
def update_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    connection = get_db_connection()
    cursor = connection.cursor()

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        address = request.form.get('address')
        contact_number = request.form.get('contact_number')
        is_staff = 1 if 'is_staff' in request.form else 0
        
        # Validate address and phone number
        if address and not is_valid_sg_address(address):
            flash('Invalid Singapore address. Please provide a valid address with a 6-digit postal code.')
            return redirect(url_for('update_account'))

        if contact_number and not is_valid_sg_phone(contact_number):
            flash('Invalid Singapore phone number. Please provide a valid 8-digit number starting with 6, 8, or 9.')
            return redirect(url_for('update_account'))

        # Check if email already exists for another user
        cursor.execute("SELECT * FROM Users WHERE Email = %s AND UserID != %s", (email, session['user_id']))
        existing_user = cursor.fetchone()

        if existing_user:
            flash('Email is already in use by another account.')
            return redirect(url_for('update_account'))

        # Update user details in the database
        cursor.execute("""
            UPDATE Users
            SET Username = %s, Email = %s, Password = %s, Address = %s, ContactNumber = %s, IsStaff = %s
            WHERE UserID = %s
        """, (username, email, password, address, contact_number, is_staff, session['user_id']))
        connection.commit()

        # Update session data with new username
        session['username'] = username
        flash('Account updated successfully!', 'success')
        return redirect(url_for('update_account'))

    # Fetch the current user's data
    cursor.execute("SELECT * FROM Users WHERE UserID = %s", (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()
    connection.close()

    return render_template('update_account.html', user=user)


# Route to delete the user's account
@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))

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
    return redirect(url_for('register'))

# Staff Dashboard route
@app.route('/staff_dashboard')
def staff_dashboard():
    if 'is_staff' in session and session['is_staff'] == 1:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Fetch all patients (IsStaff = 0)
        cursor.execute("SELECT * FROM Users WHERE IsStaff = 0")
        patients = cursor.fetchall()

        cursor.close()
        connection.close()
        return render_template('staff_dashboard.html', patients=patients)
    else:
        flash('You do not have access to this page.')
        return redirect(url_for('login'))

# Patient Dashboard route
@app.route('/patient_dashboard')
def patient_dashboard():
    if 'is_staff' in session and session['is_staff'] == 0:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Fetch user details
        cursor.execute("SELECT * FROM Users WHERE UserID = %s", (session['user_id'],))
        user = cursor.fetchone()

        # Fetch patient details
        cursor.execute("SELECT * FROM Patients WHERE UserID = %s", (session['user_id'],))
        patient = cursor.fetchone()

        # Fetch appointments for the patient
        cursor.execute("""
            SELECT ApptID, PatientID, ApptDate, ApptTime, ApptStatus, ApptReason
            FROM Appointments
            WHERE PatientID = %s
            ORDER BY ApptDate DESC, ApptTime DESC
        """, (patient['PatientID'],))
        appointments = cursor.fetchall()

        cursor.close()
        connection.close()

        return render_template('patient_dashboard.html', user=user, patient=patient, appointments=appointments)
    else:
        flash('You do not have access to this page.')
        return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
