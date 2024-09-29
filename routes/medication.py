
from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from . import medication_bp
from db import get_db_connection
import mysql.connector

@medication_bp.route('/medications')
def medications():
    # Check if the user is logged in and is staff
    if not session.get('is_staff') == 1:
        flash("You do not have permission to access the Medication List.")
        return redirect(url_for('patient.patient_dashboard'))

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
@medication_bp.route('/update_medication_quantity', methods=['POST'])
def update_medication_quantity():
    if not session.get('is_staff') == 1:
        flash("You do not have permission to update medication quantities.")
        return redirect(url_for('patient.patient_dashboard'))

    # Get the form data
    medication_id = request.form.get('medication_id')
    quantity_change = int(request.form.get('quantity_change'))

    # Check for valid input
    if not medication_id or not quantity_change:
        flash('Invalid input, please try again.', 'danger')
        return redirect(url_for('medication.medications'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)  # Ensure the cursor returns dictionaries

    # Fetch current quantity of the medication
    cursor.execute("SELECT quantity FROM Medications WHERE MedID = %s", (medication_id,))
    medication = cursor.fetchone()

    if not medication:
        flash('Medication not found.', 'danger')
        cursor.close()
        connection.close()
        return redirect(url_for('medication.medications'))

    # Update the quantity in the database
    new_quantity = medication['quantity'] + quantity_change
    cursor.execute("UPDATE Medications SET quantity = %s WHERE MedID = %s", (new_quantity, medication_id))
    connection.commit()

    flash(f'Medication ID {medication_id} updated. New quantity: {new_quantity}', 'success')

    cursor.close()
    connection.close()

    return redirect(url_for('medication.medications'))
