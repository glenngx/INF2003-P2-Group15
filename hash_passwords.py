from werkzeug.security import generate_password_hash
import mysql.connector

def hash_existing_passwords():
    # Connect to MariaDB
    connection = mysql.connector.connect(
        host='35.212.250.168',
        user='yeongchinliong',
        password='qwerty12345',
        database='project_db'
    )
    cursor = connection.cursor()

    # Fetch all users with plain-text passwords
    cursor.execute("SELECT UserID, Password FROM Users")
    users = cursor.fetchall()

    for user in users:
        user_id, plain_password = user

        # Hash the plain-text password using 'pbkdf2:sha256'
        hashed_password = generate_password_hash(plain_password, method='pbkdf2:sha256')

        # Update the user's password in the database with the hashed version
        cursor.execute("UPDATE Users SET Password = %s WHERE UserID = %s", (hashed_password, user_id))
        connection.commit()

    cursor.close()
    connection.close()
    print("Passwords updated successfully.")

# Run the function
hash_existing_passwords()
