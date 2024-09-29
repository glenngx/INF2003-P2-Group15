# routes/staff.py

from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from . import staff_bp
from db import get_db_connection
from utils import is_valid_nric, is_valid_sg_address, is_valid_sg_phone
import mysql.connector
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

# Staff Dashboard route
@staff_bp.route('/staff_dashboard', methods=['GET'])
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
        return redirect(url_for('auth.login'))
    
    # edit patient records
@staff_bp.route('/edit_patient/<int:patient_id>', methods=['GET', 'POST'])
def edit_patient(patient_id):
    if 'is_staff' not in session or session['is_staff'] != 1:
        flash('You do not have access to this page.')
        return redirect(url_for('auth.login'))

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
            
        # Fetch the existing value of is_staff from the database
        cursor.execute("SELECT IsStaff FROM Users WHERE UserID = %s", (patient_id,))
        existing_is_staff = cursor.fetchone()['IsStaff']

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
                
                # Fetch the existing hashed password from the database
                cursor.execute("SELECT Password FROM Users WHERE UserID = %s", (patient_id,))
                existing_hashed_password = cursor.fetchone()['Password']

                # Only re-hash and update the password if a new one is provided
                if password.strip():  # If a new password is entered
                    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
                    cursor.execute("""
                        UPDATE Users
                        SET Password = %s
                        WHERE UserID = %s
                    """, (hashed_password, patient_id))
                else:
                    # No need to update the password if the field is left blank
                    hashed_password = existing_hashed_password

                cursor.execute("""
                    UPDATE Users
                    SET Username = %s, Email = %s, ContactNumber = %s, Address = %s, IsStaff = %s
                    WHERE UserID = %s
                """, (username, email, contact_number, address, existing_is_staff, patient_id))

                connection.commit()
                flash('Patient details updated successfully!', 'success')
                return redirect(url_for('staff.staff_dashboard'))
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
@staff_bp.route('/delete_patient/<int:patient_id>', methods=['POST'])
def delete_patient(patient_id):
    if 'is_staff' not in session or session['is_staff'] != 1:
        flash('You do not have access to this page.')
        return redirect(url_for('auth.login'))

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

    return redirect(url_for('staff.staff_dashboard'))

@staff_bp.route('/manage_appointment')
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

@staff_bp.route('/view_patient/<int:patient_id>/<int:appt_id>', methods=['GET', 'POST'])
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

@staff_bp.route('/fetch_medications')
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

@staff_bp.route('/advanced_search', methods=['POST'])
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