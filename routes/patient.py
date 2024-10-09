# routes/patient.py

from flask import render_template, request, redirect, session, url_for, flash
from . import patient_bp
from db import get_db_connection
from utils import is_valid_sg_address, is_valid_sg_phone
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import mysql.connector

# Patient Dashboard route
@patient_bp.route('/patient_dashboard')
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

        # Fetch appointments for patient
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
        return redirect(url_for('auth.login'))
    
# Update account route
@patient_bp.route('/update_account', methods=['GET', 'POST'])
def update_account():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    connection = get_db_connection()
    cursor = connection.cursor()

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password'] 
        address = request.form.get('address')
        contact_number = request.form.get('contact_number')
        
        # Validation checks
        if address and not is_valid_sg_address(address):
            flash('Invalid Singapore address. Please provide a valid address with a 6-digit postal code.')
            return redirect(url_for('patient.update_account'))

        if contact_number and not is_valid_sg_phone(contact_number):
            flash('Invalid Singapore phone number. Please provide a valid 8-digit number starting with 6, 8, or 9.')
            return redirect(url_for('patient.update_account'))
        
        # Fetch the existing value of is_staff from DB
        cursor.execute("SELECT IsStaff FROM Users WHERE UserID = %s", (session['user_id'],))
        existing_is_staff = cursor.fetchone()[0]

        cursor.execute("SELECT * FROM Users WHERE Email = %s AND UserID != %s", (email, session['user_id']))
        existing_user = cursor.fetchone()

        if existing_user:
            flash('Email is already in use by another account.')
            return redirect(url_for('patient.update_account'))

        # Fetch hashed password from DB
        cursor.execute("SELECT Password FROM Users WHERE UserID = %s", (session['user_id'],))
        existing_hashed_password = cursor.fetchone()[0]

        # Check if there is new password, if not keep the old one
        if password.strip():
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        else:
            hashed_password = existing_hashed_password

        # Update new details into the DB
        cursor.execute("""
            UPDATE Users
            SET Username = %s, Email = %s, Password = %s, Address = %s, ContactNumber = %s, IsStaff = %s
            WHERE UserID = %s
        """, (username, email, hashed_password, address, contact_number, existing_is_staff, session['user_id']))
        connection.commit()

        # Update session data with new username
        session['username'] = username
        flash('Account updated successfully!', 'success')
        return redirect(url_for('patient.update_account'))

    # Fetch the current user's data using JOIN statement on Users and Patients tables
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

# Book and view appointment(s) route
@patient_bp.route('/book_appointment', methods=['GET', 'POST'])
def book_appointment():
    if 'user_id' not in session:
        flash('Please log in to book an appointment.')
        return redirect(url_for('auth.login'))

    if session.get('is_staff') == 1:
        flash('Staff members cannot book appointments.')
        return redirect(url_for('staff.staff_dashboard'))

    # Get the current date and the date one week from now
    # Patients should not be able to book further than that
    today = datetime.now().date()
    one_week_later = today + timedelta(days=7)

    if request.method == 'POST':
        appt_date = request.form.get('appt_date')
        appt_time = request.form.get('appt_time')
        appt_reason = request.form.get('appt_reason')

        # Validation
        if not appt_date or not appt_time or not appt_reason:
            flash('All fields are required.')
            return redirect(url_for('patient.book_appointment'))

        # Validate date and time
        try:
            appt_date_obj = datetime.strptime(appt_date, '%Y-%m-%d').date()
            appt_time_obj = datetime.strptime(appt_time, '%H:%M').time()

            # Ensure appointments are in 30-minute intervals
            if appt_time_obj.minute not in [0, 30]: 
                flash('Appointments must be booked at 30-minute intervals.')
                return redirect(url_for('patient.book_appointment'))
        except ValueError:
            flash('Invalid date or time format.')
            return redirect(url_for('patient.book_appointment'))

        # Validation for if patient books invalid time for appointment
        if appt_date_obj < datetime.today().date():
            flash('Appointment date must be in the future.')
            return redirect(url_for('patient.book_appointment'))

        # Validation for appointment date range
        if appt_date_obj < today or appt_date_obj > one_week_later:
            flash('Appointments can only be booked within the next 7 days.')
            return redirect(url_for('patient.book_appointment'))

        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            # Fetch PatientID
            cursor.execute("SELECT PatientID FROM Patients WHERE UserID = %s", (session['user_id'],))
            patient = cursor.fetchone()

            if not patient:
                flash('Patient record not found. Please contact support.')
                return redirect(url_for('patient.patient_dashboard'))

            patient_id = patient[0]

            # Check if the appointment slot is available
            cursor.execute("""
                SELECT COUNT(*) FROM Appointments 
                WHERE ApptDate = %s AND ApptTime = %s
            """, (appt_date_obj, appt_time_obj))
            existing_appointments = cursor.fetchone()[0]

            if existing_appointments > 0:
                flash('This appointment slot is already taken. Please choose another time.')
                return redirect(url_for('patient.book_appointment'))

            # Insert the appointment into the Appointments table
            cursor.execute("""
                INSERT INTO Appointments (PatientID, ApptDate, ApptTime, ApptStatus, ApptReason)
                VALUES (%s, %s, %s, %s, %s)
            """, (patient_id, appt_date_obj, appt_time_obj, 'Pending', appt_reason))
            connection.commit()

            flash('Appointment booked successfully!', 'success')
            return redirect(url_for('patient.patient_dashboard'))

        except mysql.connector.Error as err:
            print(f"Error: {err}")
            flash('An error occurred while booking the appointment. Please try again.', 'danger')
            return redirect(url_for('patient.book_appointment'))

        finally:
            cursor.close()
            connection.close()

    return render_template('book_appointment.html', min_date=today, max_date=one_week_later)