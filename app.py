from flask import Flask, redirect, session, url_for
from config import Config
from routes import auth_bp, staff_bp, patient_bp, medication_bp

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure key
app.config.from_object(Config)
app.register_blueprint(auth_bp)
app.register_blueprint(staff_bp)
app.register_blueprint(patient_bp)
app.register_blueprint(medication_bp)

@app.route('/')
def index():
    # Check if the user is logged in (session contains user information)
    if 'username' in session:
        # Redirect based on user role (is_staff)
        if session.get('is_staff') == 1:
            return redirect(url_for('staff.staff_dashboard'))
        else:
            return redirect(url_for('patient.patient_dashboard'))
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    app.run(debug=True)
