# routes/staff.py

from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from . import staff_bp
from db import get_db_connection
from utils import is_valid_nric, is_valid_sg_address, is_valid_sg_phone
import mysql.connector
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import logging

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
        diagnosis = request.args.get('diagnosis', '')  # New filter for diagnosis
        diagnosis_date = request.args.get('diagnosis_date', '')  # New filter for diagnosis date

        # Construct the query to fetch patient details
        query = """
            SELECT u.UserID, u.Username, u.Email, u.Address, u.ContactNumber, 
                   p.PatientName, p.NRIC, p.PatientGender, p.PatientHeight, 
                   p.PatientWeight, p.PatientDOB, ph.diagnosis, ph.diagnosis_date
            FROM Users u
            LEFT JOIN Patients p ON u.UserID = p.UserID
            LEFT JOIN (
                SELECT ph1.PatientID, ph1.diagnosis, ph1.date as diagnosis_date
                FROM PatientHistory ph1
                INNER JOIN (
                    SELECT PatientID, MAX(date) AS latest_date
                    FROM PatientHistory
                    GROUP BY PatientID
                ) ph2 ON ph1.PatientID = ph2.PatientID AND ph1.date = ph2.latest_date
            ) ph ON p.PatientID = ph.PatientID
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
            try:
                formatted_dob = datetime.strptime(dob, '%Y-%m-%d').date()
                filters.append("p.PatientDOB = %s")
                params.append(formatted_dob)
            except ValueError:
                logging.warning(f"Invalid date format for DOB: {dob}")
        if diagnosis:
            filters.append("ph.diagnosis LIKE %s")
            params.append(f"%{diagnosis}%")
        if diagnosis_date:
            try:
                formatted_date = datetime.strptime(diagnosis_date, '%Y-%m-%d').date()
                filters.append("DATE(ph.diagnosis_date) = %s")
                params.append(formatted_date)
            except ValueError:
                logging.warning(f"Invalid date format for diagnosis_date: {diagnosis_date}")

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
    
# Edit patient records
@staff_bp.route('/edit_patient/<int:patient_id>', methods=['GET', 'POST'])
def edit_patient(patient_id):
    # Check if user is logged in and is staff
    if 'is_staff' not in session or session['is_staff'] != 1:
        flash('You do not have access to this page.')
        return redirect(url_for('auth.login'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    errors = {}

    if request.method == 'POST':
        
        print(f"Full form data: {request.form}")
        # Retrieve form data
        patient_name = request.form['patient_name']
        nric = request.form['nric']
        patient_gender = request.form['patient_gender']
        patient_height = request.form['patient_height']
        patient_weight = request.form['patient_weight']
        patient_dob = request.form['patient_dob']
        email = request.form['email']
        username = request.form['username']
        contact_number = request.form['contact_number']
        address = request.form['address']
        password = request.form.get('password')

        # Handle past diagnosis update or add
        diagnosis_id = request.form.getlist('diagnosis_id')
        print(f"Diagnosis IDs: {diagnosis_id}")
        diagnosis_text = request.form.getlist('diagnosis_text')
        diagnosis_date = request.form.getlist('diagnosis_date')
        diagnosis_notes = request.form.getlist('diagnosis_notes')
        appt_id = request.form.getlist('appt_id')  # Fetch the ApptID list
        
        # Fetch PatientID from Patients table
        cursor.execute("SELECT PatientID FROM Patients WHERE UserID = %s", (patient_id,))
        patient_data = cursor.fetchone()
        if not patient_data:
            flash('Patient not found.', 'danger')
            return redirect(url_for('staff.staff_dashboard'))

        actual_patient_id = patient_data['PatientID']  # Use PatientID instead of UserID

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
        cursor.execute("SELECT IsStaff FROM Users WHERE UserID = %s", (patient_id,))
        existing_is_staff = cursor.fetchone()['IsStaff']

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
                # Handle empty height and weight fields
                patient_height = patient_height if patient_height.strip() else None
                patient_weight = patient_weight if patient_weight.strip() else None
                
                # Update Patients table
                cursor.execute("""
                    UPDATE Patients
                    SET PatientName = %s, NRIC = %s, PatientGender = %s, PatientHeight = %s, 
                        PatientWeight = %s, PatientDOB = %s
                    WHERE UserID = %s
                """, (patient_name, nric, patient_gender, patient_height, patient_weight, patient_dob, patient_id))

                # Update password if provided
                cursor.execute("SELECT Password FROM Users WHERE UserID = %s", (patient_id,))
                existing_hashed_password = cursor.fetchone()['Password']

                if password and password.strip():  # If a new password is provided
                    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
                    cursor.execute("""
                        UPDATE Users
                        SET Password = %s
                        WHERE UserID = %s
                    """, (hashed_password, patient_id))

                # Update Users table for other details
                cursor.execute("""
                    UPDATE Users
                    SET Username = %s, Email = %s, ContactNumber = %s, Address = %s, IsStaff = %s
                    WHERE UserID = %s
                """, (username, email, contact_number, address, existing_is_staff, patient_id))

                # Handle diagnosis updates and inserts
                for idx, diag_id in enumerate(diagnosis_id):
                    
                    # If diagnosis ID (history_id) exists, update the existing diagnosis
                    if diag_id:
                        cursor.execute("""
                            UPDATE PatientHistory 
                            SET diagnosis = %s, date = %s, notes = %s, ApptID = %s
                            WHERE history_id = %s AND PatientID = %s
                        """, (diagnosis_text[idx], diagnosis_date[idx], diagnosis_notes[idx], appt_id[idx], diag_id, actual_patient_id))

                # Commit all changes to the database
                connection.commit()

                flash('Patient details and diagnoses updated successfully!', 'success')
                return redirect(url_for('staff.staff_dashboard'))
            except mysql.connector.Error as err:
                connection.rollback()  # Rollback in case of any error
                flash(f'An error occurred: {err}', 'danger')

    # Fetch patient details including UserID and PatientID
    cursor.execute("SELECT UserID, PatientID, PatientName, NRIC, PatientGender, PatientHeight, PatientWeight, PatientDOB FROM Patients WHERE UserID = %s", (patient_id,))
    patient = cursor.fetchone()

    if not patient:
        flash('Patient not found', 'danger')
        return redirect(url_for('staff.staff_dashboard'))

    # Fetch user details related to the patient
    cursor.execute("SELECT * FROM Users WHERE UserID = %s", (patient_id,))
    user = cursor.fetchone()

    # Fetch past diagnoses using PatientID
    cursor.execute("SELECT history_id, ApptID, diagnosis, date, notes FROM PatientHistory WHERE PatientID = %s ORDER BY date DESC", (patient['PatientID'],))
    patient_diagnoses = cursor.fetchall()

    # Format diagnosis dates to 'YYYY-MM-DD' for display
    for diag in patient_diagnoses:
        if diag['date']:
            diag['date'] = diag['date'].strftime('%Y-%m-%d')

    # Close cursor and connection
    cursor.close()
    connection.close()

    return render_template('edit_patient.html', patient=patient, user=user, diagnoses=patient_diagnoses, errors=errors)




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

# View patient details
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

# Fetch medications
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
        'diagnosis': request.form.get('diagnosis'),
        'diagnosis_date': request.form.get('diagnosis_date')
    }

    query = """
    SELECT u.UserID, u.Username, u.Email, u.Address, u.ContactNumber, 
           p.PatientName, p.NRIC, p.PatientGender, p.PatientHeight, 
           p.PatientWeight, p.PatientDOB, ph.diagnosis, ph.diagnosis_date
    FROM Users u
    LEFT JOIN Patients p ON u.UserID = p.UserID
    LEFT JOIN (
        SELECT ph1.PatientID, ph1.diagnosis, ph1.date AS diagnosis_date
        FROM PatientHistory ph1
        INNER JOIN (
            SELECT PatientID, MAX(date) AS latest_date
            FROM PatientHistory
            GROUP BY PatientID
        ) ph2 ON ph1.PatientID = ph2.PatientID AND ph1.date = ph2.latest_date
    ) ph ON p.PatientID = ph.PatientID
    WHERE u.IsStaff = 0
    """

    conditions = []
    params = []

    # Add filters dynamically if they exist
    for field, value in filters.items():
        if value:
            if field in ['Username', 'Email', 'Address', 'ContactNumber', 'PatientName', 'NRIC',
                         'diagnosis']:  # Adjusted field list
                conditions.append(f"{field} LIKE %s")
                params.append(f"%{value}%")
            elif field == 'PatientGender':
                gender_map = {'Male': 'M', 'Female': 'F'}
                conditions.append(f"p.PatientGender = %s")
                params.append(gender_map.get(value, value))
            elif field in ['PatientHeight', 'PatientWeight']:
                try:
                    float_value = float(value)
                    conditions.append(f"ABS(p.{field} - %s) < 0.01")
                    params.append(float_value)
                except ValueError:
                    pass
            elif field == 'PatientDOB':
                conditions.append(f"p.PatientDOB = %s")
                params.append(value)
            elif field == 'diagnosis_date':
                try:
                    formatted_date = datetime.strptime(value, '%Y-%m-%d').date()
                    conditions.append(f"DATE(ph.diagnosis_date) = %s")
                    params.append(formatted_date)
                except ValueError:
                    logging.warning(f"Invalid date format for diagnosis_date: {value}")
                    continue

    # Add conditions to the query
    if conditions:
        query += " AND " + " AND ".join(conditions)

    query += " ORDER BY u.UserID"

    # Execute the query
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(query, params)
    results = cursor.fetchall()

    for result in results:  # Ensure that DOB is formatted correctly
        if result['PatientDOB']:
            result['PatientDOB'] = result['PatientDOB'].strftime('%Y-%m-%d')
        if result['diagnosis_date']:  # Ensure diagnosis_date is formatted correctly
            result['diagnosis_date'] = result['diagnosis_date'].strftime('%Y-%m-%d')

    cursor.close()
    connection.close()

    return jsonify(results)

@staff_bp.route('/edit_appointment/<int:appt_id>', methods=['GET', 'POST'])
def edit_appointment(appt_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    if request.method == 'POST':
        # If the form is submitted, update the appointment details.
        date = request.form['date']
        time = request.form['time']
        status = request.form['status']
        reason = request.form['reason']

        cursor.execute("""
            UPDATE Appointments 
            SET ApptDate = %s, ApptTime = %s, ApptStatus = %s, ApptReason = %s 
            WHERE ApptID = %s
        """, (date, time, status, reason, appt_id))

        connection.commit()
        flash('Appointment updated successfully!', 'success')
        return redirect(url_for('staff.manage_appointment'))  # Redirect to appointments list after updating

    # If it's a GET request, fetch the current appointment details.
    cursor.execute("SELECT * FROM Appointments WHERE ApptID = %s", (appt_id,))
    appointment = cursor.fetchone()

    cursor.close()
    connection.close()
    
    return render_template('edit_appointment.html', appointment=appointment)

@staff_bp.route('/staff_book_appointment', methods=['GET', 'POST'])
def staff_book_appointment():
    if 'user_id' not in session:
        flash('Please log in as staff to book an appointment.')
        return redirect(url_for('auth.login'))

    # Get the current date and the date one week from now
    today = datetime.now().date()
    one_week_later = today + timedelta(days=7)

    if request.method == 'POST':
        # Collect form data
        nric = request.form.get('patient_nric')
        appt_date = request.form.get('appt_date')
        appt_time = request.form.get('appt_time')
        appt_reason = request.form.get('appt_reason')

        # Basic validation
        if not nric or not appt_date or not appt_time or not appt_reason:
            flash('All fields are required.')
            return redirect(url_for('staff.staff_book_appointment'))

        try:
            appt_date_obj = datetime.strptime(appt_date, '%Y-%m-%d').date()
            appt_time_obj = datetime.strptime(appt_time, '%H:%M').time()
            if appt_time_obj.minute not in [0, 30]:
                flash('Appointments must be booked at 30-minute intervals.')
                return redirect(url_for('staff.staff_book_appointment'))
        except ValueError:
            flash('Invalid date or time format.')
            return redirect(url_for('staff.staff_book_appointment'))

        if appt_date_obj < datetime.today().date():
            flash('Appointment date must be in the future.')
            return redirect(url_for('staff.staff_book_appointment'))

        if appt_date_obj < today or appt_date_obj > one_week_later:
            flash('Appointments can only be booked within the next 7 days.')
            return redirect(url_for('staff.staff_book_appointment'))

        # Connect to the database
        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            # Check if the patient exists
            cursor.execute("SELECT PatientID FROM Patients WHERE nric = %s", (nric,))
            patient = cursor.fetchone()

            if not patient:
                flash('Patient NRIC not found. Please contact support.')
                return redirect(url_for('staff.staff_book_appointment'))

            patient_id = patient[0]  # Get the PatientID from the result
            
            # Check if the appointment slot is available
            cursor.execute("""
                SELECT COUNT(*) FROM Appointments 
                WHERE ApptDate = %s AND ApptTime = %s
            """, (appt_date_obj, appt_time_obj))
            existing_appointments = cursor.fetchone()[0]

            if existing_appointments > 0:
                flash('This appointment slot is already taken. Please choose another time.')
                return redirect(url_for('staff.staff_book_appointment'))

            # Insert the appointment into the Appointments table
            cursor.execute("""
                INSERT INTO Appointments (PatientID, ApptDate, ApptTime, ApptStatus, ApptReason)
                VALUES (%s, %s, %s, %s, %s)
            """, (patient_id, appt_date_obj, appt_time_obj, 'Pending', appt_reason))
            connection.commit()

            flash('Appointment booked successfully!', 'success')
            return redirect(url_for('staff.staff_dashboard'))

        except mysql.connector.Error as err:
            print(f"Error: {err}")
            flash('An error occurred while booking the appointment. Please try again.', 'danger')
            return redirect(url_for('staff.staff_book_appointment'))

        finally:
            cursor.close()
            connection.close()

    return render_template('staff_book_appointment.html', min_date=today, max_date=one_week_later)

@staff_bp.route('/delete_appointment/<int:appt_id>', methods=['POST'])
def delete_appointment(appt_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("DELETE FROM Appointments WHERE ApptID = %s", (appt_id,))
    connection.commit()
    
    flash('Appointment deleted successfully!', 'success')
    cursor.close()
    connection.close()
    
    return redirect(url_for('staff.manage_appointment'))  # Redirect to appointments list