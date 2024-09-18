from flask import Flask, render_template, request, redirect, session, url_for, flash
import re
import mysql.connector

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

# User registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        address = request.form.get('address')  # Optional field
        contact_number = request.form.get('contact_number')  # Optional field
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
                flash('Welcome, staff member!')
                return redirect(url_for('staff_dashboard'))
            else:  # If IsStaff is 0, it's a patient
                flash('Welcome, patient!')
                return redirect(url_for('patient_dashboard'))
        else:
            flash('Invalid login credentials.')
            return redirect(url_for('login'))

    return render_template('login.html')

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
        cursor = connection.cursor()

        # Fetch patient details (the current logged-in patient)
        cursor.execute("SELECT * FROM Users WHERE UserID = %s", (session['user_id'],))
        patient = cursor.fetchone()

        cursor.close()
        connection.close()
        return render_template('patient_dashboard.html', patient=patient)
    else:
        flash('You do not have access to this page.')
        return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
