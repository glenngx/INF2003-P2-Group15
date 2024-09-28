from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
import re
import mysql.connector
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

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

# Validate NRIC format
def is_valid_nric(nric):
    """Check if the NRIC is valid: starts with (S,T,F,G,M), followed by 7 digits and one letter."""
    return re.match(r'^[STFGMstfgm]\d{7}[A-Za-z]$', nric)

@app.route('/')
def index():
    # Check if the user is logged in (session contains user information)
    if 'username' in session:
        # Redirect based on user role (is_staff)
        if session.get('is_staff') == 1:
            return redirect(url_for('staff_dashboard'))
        else:
            return redirect(url_for('patient_dashboard'))
    return redirect(url_for('login'))

# User registration route
@app.route('/register', methods=['GET', 'POST'])
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
        return redirect(url_for('login'))

    return render_template('register.html')

# User login route
@app.route('/login', methods=['GET', 'POST'])
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
            return redirect(url_for('login'))

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
    errors = {}

    if request.method == 'POST':
        patient_name = request.form['patient_name']
        nric = request.form['nric']
        patient_gender = request.form['patient_gender']
        patient_height = request.form['patient_height']
        patient_weight = request.form['patient_weight']
        patient_dob = request.form['patient_dob']
        patient_conditions = request.form['patient_conditions']
        email = request.form['email']
        username = request.form['username']
        contact_number = request.form['contact_number']
        address = request.form['address']
        password = request.form.get('password')

        # Validate NRIC format
        if not is_valid_nric(nric):
            errors['nric'] = 'Invalid NRIC format. It must start with S, T, F, G, or M, followed by 7 digits and one letter.'

        # Validate phone number
        if not is_valid_sg_phone(contact_number):
            errors['contact_number'] = 'Invalid phone number format. It must start with 6, 8, or 9 and be 8 digits long.'

        # Validate address for Singapore postal code
        if not is_valid_sg_address(address):
            errors['address'] = 'Invalid address. Please include a valid 6-digit postal code.'

        # Check for duplicates in the database
        cursor.execute("SELECT * FROM Users WHERE (Email = %s OR ContactNumber = %s OR Username = %s) AND UserID != %s",
                       (email, contact_number, username, patient_id))
        existing_user = cursor.fetchone()

        cursor.execute("SELECT * FROM Patients WHERE NRIC = %s AND UserID != %s", (nric, patient_id))
        existing_nric = cursor.fetchone()

        if existing_user:
            if existing_user['Email'] == email:
                errors['email'] = 'Email is already in use.'
            if existing_user['ContactNumber'] == contact_number:
                errors['contact_number'] = 'Contact number is already in use.'
            if existing_user['Username'] == username:
                errors['username'] = 'Username is already in use.'

        if existing_nric:
            errors['nric'] = 'NRIC is already in use.'

        # If no errors, update the patient details in the database
        if not errors:
            try:
                cursor.execute("""
                    UPDATE Patients
                    SET PatientName = %s, NRIC = %s, PatientGender = %s, PatientHeight = %s, 
                        PatientWeight = %s, PatientDOB = %s, PatientConditions = %s
                    WHERE UserID = %s
                """, (patient_name, nric, patient_gender, patient_height, patient_weight, patient_dob, patient_conditions, patient_id))
                
                if password:  # Only update password if it's provided
                    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
                    cursor.execute("""
                        UPDATE Users
                        SET Password = %s
                        WHERE UserID = %s
                    """, (hashed_password, patient_id))

                cursor.execute("""
                    UPDATE Users
                    SET Username = %s, Email = %s, ContactNumber = %s, Address = %s
                    WHERE UserID = %s
                """, (username, email, contact_number, address, patient_id))

                connection.commit()
                flash('Patient details updated successfully!', 'success')
                return redirect(url_for('staff_dashboard'))
            except mysql.connector.Error as err:
                flash(f'An error occurred: {err}', 'danger')

    # Fetch patient details
    cursor.execute("SELECT * FROM Patients WHERE UserID = %s", (patient_id,))
    patient = cursor.fetchone()

    # Fetch user details (related to patient)
    cursor.execute("SELECT * FROM Users WHERE UserID = %s", (patient_id,))
    user = cursor.fetchone()

    cursor.close()
    connection.close()

    return render_template('edit_patient.html', patient=patient, user=user, errors=errors)


# Delete patient records
@app.route('/delete_patient/<int:patient_id>', methods=['POST'])
def delete_patient(patient_id):
    if 'is_staff' not in session or session['is_staff'] != 1:
        flash('You do not have access to this page.')
        return redirect(url_for('login'))

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # First delete the patient's appointments
        cursor.execute("DELETE FROM Appointments WHERE PatientID = (SELECT PatientID FROM Patients WHERE UserID = %s)", (patient_id,))

        # Then delete the patient from the Patients table
        cursor.execute("DELETE FROM Patients WHERE UserID = %s", (patient_id,))

        # Finally, delete the user from the Users table
        cursor.execute("DELETE FROM Users WHERE UserID = %s", (patient_id,))

        connection.commit()
        flash('Patient and associated appointments deleted successfully!', 'success')
    except mysql.connector.Error as err:
        connection.rollback()
        flash(f'An error occurred: {err}', 'danger')

    cursor.close()
    connection.close()

    return redirect(url_for('staff_dashboard'))

# Route to book and view appointment
@app.route('/book_appointment', methods=['GET', 'POST'])
def book_appointment():
    if 'user_id' not in session:
        flash('Please log in to book an appointment.')
        return redirect(url_for('login'))

    if session.get('is_staff') == 1:
        flash('Staff members cannot book appointments.')
        return redirect(url_for('staff_dashboard'))

    # Get the current date and the date one week from now
    today = datetime.now().date()
    one_week_later = today + timedelta(days=7)

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
            # Ensure the appointment is in 30-minute intervals
            if appt_time_obj.minute not in [0, 30]:
                flash('Appointments must be booked at 30-minute intervals.')
                return redirect(url_for('book_appointment'))
        except ValueError:
            flash('Invalid date or time format.')
            return redirect(url_for('book_appointment'))

        # Validation for if patient books invalid time for appointment
        if appt_date_obj < datetime.today().date():
            flash('Appointment date must be in the future.')
            return redirect(url_for('book_appointment'))

        # Validation for appointment date range
        if appt_date_obj < today or appt_date_obj > one_week_later:
            flash('Appointments can only be booked within the next 7 days.')
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

            # Check if the appointment slot is available
            cursor.execute("""
                SELECT COUNT(*) FROM Appointments 
                WHERE ApptDate = %s AND ApptTime = %s
            """, (appt_date_obj, appt_time_obj))
            existing_appointments = cursor.fetchone()[0]

            if existing_appointments > 0:
                flash('This appointment slot is already taken. Please choose another time.')
                return redirect(url_for('book_appointment'))

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

    return render_template('book_appointment.html', min_date=today, max_date=one_week_later)

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
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
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
        """, (username, email, hashed_password, address, contact_number, is_staff, session['user_id']))
        connection.commit()

        # Update session data with new username
        session['username'] = username
        flash('Account updated successfully!', 'success')
        return redirect(url_for('update_account'))

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
@app.route('/staff_dashboard', methods=['GET'])
def staff_dashboard():
    if 'is_staff' in session and session['is_staff'] == 1:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Get filter values from the request (GET parameters)
        user_id = request.args.get('user_id', '')
        username = request.args.get('username', '')
        email = request.args.get('email', '')
        address = request.args.get('address', '')
        contact_number = request.args.get('contact_number', '')
        name = request.args.get('name', '')
        nric = request.args.get('nric', '')
        gender = request.args.get('gender', '')
        height = request.args.get('height', '')
        weight = request.args.get('weight', '')
        dob = request.args.get('dob', '')

        # Start building the SQL query
        query = """
            SELECT u.UserID, u.Username, u.Email, u.Address, u.ContactNumber, 
                   p.PatientName, p.NRIC, p.PatientGender, p.PatientHeight, 
                   p.PatientWeight, p.PatientDOB, p.PatientConditions
            FROM Users u
            LEFT JOIN Patients p ON u.UserID = p.UserID
            WHERE u.IsStaff = 0
        """
        
        filters = []
        params = []

        # Add filters dynamically if they exist
        if user_id:
            filters.append("u.UserID = %s")
            params.append(user_id)
        if username:
            filters.append("u.Username LIKE %s")
            params.append(f"%{username}%")
        if email:
            filters.append("u.Email LIKE %s")
            params.append(f"%{email}%")
        if address:
            filters.append("u.Address LIKE %s")
            params.append(f"%{address}%")
        if contact_number:
            filters.append("u.ContactNumber LIKE %s")
            params.append(f"%{contact_number}%")
        if name:
            filters.append("p.PatientName LIKE %s")
            params.append(f"%{name}%")
        if nric:
            filters.append("p.NRIC LIKE %s")
            params.append(f"%{nric}%")
        if gender:
            filters.append("p.PatientGender = %s")
            params.append(gender)
        if height:
            filters.append("p.PatientHeight = %s")
            params.append(height)
        if weight:
            filters.append("p.PatientWeight = %s")
            params.append(weight)
        if dob:
            filters.append("p.PatientDOB = %s")
            params.append(dob)

        # If there are filters, append them to the query
        if filters:
            query += " AND " + " AND ".join(filters)

        # Execute the query with parameters
        cursor.execute(query, params)
        patients = cursor.fetchall()

        cursor.close()
        connection.close()

        # Render the template with the filtered patient data
        return render_template('staff_dashboard.html', patients=patients)
    else:
        flash('Please login or create a new account to access our services.')
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
        flash('Please login or create a new account to access our services.')
        return redirect(url_for('login'))

@app.route('/medications')
def medications():
    # Check if the user is logged in and is staff
    if not session.get('is_staff') == 1:
        flash("You do not have permission to access the Medication List.")
        return redirect(url_for('patient_dashboard'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Get the search query from the URL parameters (GET request)
    search_query = request.args.get('search')

    if search_query:
        # If there's a search query, filter medications by the name using SQL LIKE
        cursor.execute("SELECT * FROM Medications WHERE name LIKE %s", ('%' + search_query + '%',))
    else:
        # Otherwise, fetch all medications
        cursor.execute("SELECT * FROM Medications")

    medications = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('medications.html', medications=medications)

# Route to handle medication quantity updates
@app.route('/update_medication_quantity', methods=['POST'])
def update_medication_quantity():
    if not session.get('is_staff') == 1:
        flash("You do not have permission to update medication quantities.")
        return redirect(url_for('patient_dashboard'))

    # Get the form data
    medication_id = request.form.get('medication_id')
    quantity_change = int(request.form.get('quantity_change'))

    # Check for valid input
    if not medication_id or not quantity_change:
        flash('Invalid input, please try again.', 'danger')
        return redirect(url_for('medications'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)  # Ensure the cursor returns dictionaries

    # Fetch current quantity of the medication
    cursor.execute("SELECT quantity FROM Medications WHERE MedID = %s", (medication_id,))
    medication = cursor.fetchone()

    if not medication:
        flash('Medication not found.', 'danger')
        cursor.close()
        connection.close()
        return redirect(url_for('medications'))

    # Update the quantity in the database
    new_quantity = medication['quantity'] + quantity_change
    cursor.execute("UPDATE Medications SET quantity = %s WHERE MedID = %s", (new_quantity, medication_id))
    connection.commit()

    flash(f'Medication ID {medication_id} updated. New quantity: {new_quantity}', 'success')

    cursor.close()
    connection.close()

    return redirect(url_for('medications'))

@app.route('/advanced_search', methods=['POST'])
def advanced_search():
    if 'is_staff' not in session or session['is_staff'] != 1:
        return jsonify({'error': 'Unauthorized'}), 403

    # Get search parameters from the form
    filters = {
        'Username': request.form.get('username'),
        'Email': request.form.get('email'),
        'Address': request.form.get('address'),
        'ContactNumber': request.form.get('contact_number'),
        'PatientName': request.form.get('patient_name'),
        'NRIC': request.form.get('nric'),
        'PatientGender': request.form.get('gender'),
        'PatientHeight': request.form.get('height'),
        'PatientWeight': request.form.get('weight'),
        'PatientDOB': request.form.get('dob'),
        'PatientConditions': request.form.get('conditions')
    }

    query = """
    SELECT u.UserID, u.Username, u.Email, u.Address, u.ContactNumber, 
           p.PatientName, p.NRIC, p.PatientGender, p.PatientHeight, 
           p.PatientWeight, p.PatientDOB, p.PatientConditions
    FROM Users u
    LEFT JOIN Patients p ON u.UserID = p.UserID
    WHERE u.IsStaff = 0
    """

    conditions = []
    params = []

    for field, value in filters.items():
        if value:
            if field in ['Username', 'Email', 'Address', 'ContactNumber', 'PatientName', 'NRIC', 'PatientConditions']:
                conditions.append(f"{field} LIKE %s")
                params.append(f"%{value}%")
            elif field == 'PatientGender':
                gender_map = {'Male': 'M', 'Female': 'F'}
                conditions.append(f"{field} = %s")
                params.append(gender_map.get(value, value))
            elif field in ['PatientHeight', 'PatientWeight']:
                # Handle decimal values for height and weight
                try:
                    float_value = float(value)
                    conditions.append(f"ABS({field} - %s) < 0.01")
                    params.append(float_value)
                except ValueError:
                    # If the value is not a valid float, ignore this filter
                    pass
            elif field == 'PatientDOB':
                conditions.append(f"{field} = %s")
                params.append(value)

    if conditions:
        query += " AND " + " AND ".join(conditions)

    query += " ORDER BY u.UserID"

    # Execute the query
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(query, params)
    results = cursor.fetchall()
    for result in results:  # exclude time from DOB for advanced search
        if result['PatientDOB']:
            result['PatientDOB'] = result['PatientDOB'].strftime('%Y-%m-%d')
    cursor.close()
    connection.close()

    return jsonify(results)

from datetime import datetime, timedelta

@app.route('/manage_appointment')
def manage_appointment():
    if 'is_staff' in session and session['is_staff'] == 1:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Calculate the date range for the next 7 days
        start_date = datetime.now()
        end_date = start_date + timedelta(days=7)

        # Fetch appointments in the next 7 days
        cursor.execute("""
            SELECT * FROM Appointments 
            WHERE ApptDate BETWEEN %s AND %s
        """, (start_date.date(), end_date.date()))
        appointments = cursor.fetchall()

        cursor.close()
        connection.close()
        return render_template('manage_appointment.html', appointments=appointments)
    else:
        flash('Please login or create a new account to access our services.')

@app.route('/view_patient/<int:patient_id>/<int:appt_id>', methods=['GET', 'POST'])
def view_patient(patient_id, appt_id):
    connection = get_db_connection()
    cursor = connection.cursor(buffered=True)

    if request.method == 'POST':
        # Check if we are saving a prescription
        if 'medication' in request.form:
            medication_name = request.form['medication']
            duration = request.form['duration']
            notes = request.form['notes']

            # Fetch the MedID based on medication name
            cursor.execute("SELECT MedID, quantity FROM Medications WHERE name = %s", (medication_name,))
            med = cursor.fetchone()

            if med:
                med_id = med[0]
                current_quantity = med[1]
                requested_dosage = int(duration)  # Assuming 'duration' is the amount to be taken
                print(current_quantity, type(current_quantity))
                print(requested_dosage, type(requested_dosage))
                # Check if enough medication is available
                if current_quantity >= requested_dosage:
                    # Insert into Prescriptions table
                    cursor.execute("""
                        INSERT INTO Prescriptions (PatientID, ApptID, MedID, Dosage, Date, Notes) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (patient_id, appt_id, med_id, requested_dosage, datetime.now(), notes))
                    
                    # Deduct the quantity
                    new_quantity = current_quantity - requested_dosage
                    cursor.execute("UPDATE Medications SET quantity = %s WHERE MedID = %s", (new_quantity, med_id))

                    # Insert log into Inventory logs
                    cursor.execute("""
                        INSERT INTO InventoryLogs (MedID, change_type, quantity_changed, date) 
                        VALUES (%s, 'subtract', %s, %s)
                    """, (med_id, requested_dosage, datetime.now()))

                    connection.commit()
                    flash('Prescription added successfully!', 'success')
                else:
                    flash('Not enough medication in stock!', 'danger')
            else:
                flash('Medication not found!', 'danger')

        else:
            # Save the diagnosis and notes (existing functionality)
            diagnosis = request.form['diagnosis']
            notes = request.form['notes']
            date = datetime.now()

            cursor.execute("""
                INSERT INTO PatientHistory (PatientID, ApptID, diagnosis, notes, date) 
                VALUES (%s, %s, %s, %s, %s)
            """, (patient_id, appt_id, diagnosis, notes, date))

            connection.commit()
            flash('Patient history updated successfully!', 'success')

    # Fetch patient information
    cursor.execute("SELECT * FROM Patients WHERE PatientID = %s", (patient_id,))
    patient_info = cursor.fetchone()

    # Fetch patient's past diagnoses
    cursor.execute("SELECT * FROM PatientHistory WHERE PatientID = %s", (patient_id,))
    patient_history = cursor.fetchall()

    cursor.close()
    connection.close()
    return render_template('view_patient.html', patient=patient_info, history=patient_history, appt_id=appt_id)

@app.route('/fetch_medications')
def fetch_medications():
    query = request.args.get('query', '')
    connection = get_db_connection()
    cursor = connection.cursor()

    # Fetch medications that match the user's input
    cursor.execute("SELECT * FROM Medications WHERE LOWER(name) LIKE %s", (f'%{query}%',))
    medications = cursor.fetchall()
    
    cursor.close()
    connection.close()
    
    # Prepare response data
    medication_list = [{'name': med[1]} for med in medications] # Assuming index 1 corresponds to medication name
    return jsonify(medication_list)

if __name__ == '__main__':
    app.run(debug=True)
