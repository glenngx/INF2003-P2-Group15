from flask import Flask, render_template, request, redirect, session, url_for, flash
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

# User registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        connection = get_db_connection()
        cursor = connection.cursor()

        # Check if email already exists
        cursor.execute("SELECT * FROM Users WHERE Email = %s", (email,))
        user = cursor.fetchone()

        if user:
            flash('Email already registered. Please try a different email.')
            return redirect(url_for('register'))

        # Insert new user into the database
        cursor.execute("INSERT INTO Users (Username, Email, Password) VALUES (%s, %s, %s)",
                       (username, email, password))
        connection.commit()
        cursor.close()
        connection.close()

        flash('Account created successfully! Please log in.')
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
            return redirect(url_for('index'))
        else:
            # Flash message for invalid credentials
            flash('Invalid username or password. Please try again.')
            return redirect(url_for('login'))

    return render_template('login.html')



# User logout route
@app.route('/logout')
def logout():
    session.clear()  # Clear session data
    return redirect(url_for('login'))

# Home route: Show all users and display logged-in username
@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM Users")
    users = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('index.html', users=users)

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

        # Check if email already exists for another user
        cursor.execute("SELECT * FROM Users WHERE Email = %s AND UserID != %s", (email, session['user_id']))
        existing_user = cursor.fetchone()

        if existing_user:
            flash('Email is already in use by another account.')
            return redirect(url_for('update_account'))

        # Update user details in the database
        cursor.execute("""
            UPDATE Users
            SET Username = %s, Email = %s, Password = %s
            WHERE UserID = %s
        """, (username, email, password, session['user_id']))
        connection.commit()

        # Update session data with new username
        session['username'] = username
        flash('Account updated successfully!')
        return redirect(url_for('index'))

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
    flash('Your account has been deleted successfully.')
    return redirect(url_for('register'))

if __name__ == '__main__':
    app.run(debug=True)
