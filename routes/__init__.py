# routes/__init__.py

from flask import Blueprint

auth_bp = Blueprint('auth', __name__)
staff_bp = Blueprint('staff', __name__)
patient_bp = Blueprint('patient', __name__)
medication_bp = Blueprint('medication', __name__)

from . import auth, staff, patient, medication