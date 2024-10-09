from flask import render_template, request, redirect, session, url_for, flash
from . import medication_bp
from db import get_db_connection
from datetime import datetime

@medication_bp.route('/medications')
def medications():
    if not session.get('is_staff') == 1:
        flash("You do not have permission to access the Medication List.")
        return redirect(url_for('patient.patient_dashboard'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Get the search query from the URL parameters (GET request)
    search_query = request.args.get('search')

    if search_query:
        # Filter medications by the name LIKE operation
        cursor.execute("SELECT * FROM Medications WHERE name LIKE %s ORDER BY name ASC", ('%' + search_query + '%',))
    else:
        # Fetch all medications sorted ASC by name
        cursor.execute("SELECT * FROM Medications ORDER BY name ASC")

    medications = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('medications.html', medications=medications)

# Medication quantity updates route
@medication_bp.route('/update_medication_quantity', methods=['POST'])
def update_medication_quantity():
    if not session.get('is_staff') == 1:
        flash("You do not have permission to update medication quantities.")
        return redirect(url_for('patient.patient_dashboard'))

    # Get the form data
    medication_id = request.form.get('medication_id')
    quantity_change = int(request.form.get('quantity_change'))

    # Check for valid medication and quantity
    if not medication_id or not quantity_change:
        flash('Invalid input, please try again.', 'danger')
        return redirect(url_for('medication.medications'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch current quantity of the medication
    cursor.execute("SELECT quantity FROM Medications WHERE MedID = %s", (medication_id,))
    medication = cursor.fetchone()

    if not medication:
        flash('Medication not found.', 'danger')
        cursor.close()
        connection.close()
        return redirect(url_for('medication.medications'))

    # Update the quantity in the DB
    new_quantity = medication['quantity'] + quantity_change
    cursor.execute("UPDATE Medications SET quantity = %s WHERE MedID = %s", (new_quantity, medication_id))

    # Based on the user input if they used - or not, add a tracking log to InventoryLogs table
    if quantity_change > 0:
        change_type = 'addition'
    elif quantity_change < 0:
        change_type = 'subtract'

    cursor.execute("""
                        INSERT INTO InventoryLogs (MedID, change_type, quantity_changed, date) 
                        VALUES (%s, %s, %s, %s)
                    """, (medication_id, change_type,quantity_change, datetime.now()))
    
    connection.commit()

    flash(f'Medication ID {medication_id} updated. New quantity: {new_quantity}', 'success')

    cursor.close()
    connection.close()

    return redirect(url_for('medication.medications'))

# Adding med route
@medication_bp.route('/manage_medication', methods=['POST'])
def manage_medication():
    if not session.get('is_staff') == 1:
        flash("You do not have permission to add medications.")
        return redirect(url_for('patient.patient_dashboard'))

    # Get form data
    name = request.form.get('name')
    form = request.form.get('form')
    dosage = request.form.get('dosage')
    quantity = request.form.get('quantity')
    indication = request.form.get('indication')

    if not (name and form and dosage and quantity and indication):
        flash('All fields are required to add a medication.', 'danger')
        return redirect(url_for('medication.medications'))

    connection = get_db_connection()
    cursor = connection.cursor()

    # INSERT new med into DB
    cursor.execute("INSERT INTO Medications (name, form, dosage, quantity, indication) VALUES (%s, %s, %s, %s, %s)",
                   (name, form, dosage, quantity, indication))
    connection.commit()

    flash(f'Medication "{name}" added successfully.', 'success')

    cursor.close()
    connection.close()

    return redirect(url_for('medication.medications'))

# Deleting med route
@medication_bp.route('/delete_medication', methods=['POST'])
def delete_medication():
    if not session.get('is_staff') == 1:
        flash("You do not have permission to delete medications.")
        return redirect(url_for('patient.patient_dashboard'))

    medication_id = request.form.get('medication_id')

    if not medication_id:
        flash('Invalid medication ID, please try again.', 'danger')
        return redirect(url_for('medication.medications'))

    connection = get_db_connection()
    cursor = connection.cursor()

    # Pre-check to see if med already exsist
    cursor.execute("SELECT * FROM Medications WHERE MedID = %s", (medication_id,))
    medication = cursor.fetchone()

    if not medication:
        flash('Medication not found.', 'danger')
        cursor.close()
        connection.close()
        return redirect(url_for('medication.medications'))

    # Delete the med from DB
    cursor.execute("DELETE FROM Medications WHERE MedID = %s", (medication_id,))
    connection.commit()

    flash(f'Medication ID {medication_id} deleted successfully.', 'success')

    cursor.close()
    connection.close()

    return redirect(url_for('medication.medications'))
