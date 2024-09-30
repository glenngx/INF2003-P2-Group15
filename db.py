#db.py

import mysql.connector
from config import Config

# Connect to MariaDB
def get_db_connection():
    connection = mysql.connector.connect(
        host=Config.DATABASE_HOST,
        user=Config.DATABASE_USER,
        password=Config.DATABASE_PASSWORD,
        database=Config.DATABASE_NAME,
        charset='utf8mb4',
        collation='utf8mb4_general_ci'
    )
    return connection