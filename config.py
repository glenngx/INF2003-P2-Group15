#config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your_secret_key')
    DATABASE_HOST = '35.212.250.168'
    DATABASE_USER = 'yeongchinliong'
    DATABASE_PASSWORD = 'qwerty12345'
    DATABASE_NAME = 'project_db'