import re

# Validation functions
def is_valid_sg_address(address):
    """Check if the address contains a 6-digit Singapore postal code."""
    # Check if there's a 6-digit number anywhere in the address
    return re.search(r'\b\d{6}\b', address) is not None

def is_valid_sg_phone(phone):
    """Check if the phone number is a valid Singapore number (starts with 6, 8, or 9 and is 8 digits long)."""
    return re.match(r'^[689]\d{7}$', phone) is not None

# Validate NRIC format
def is_valid_nric(nric):
    """Check if the NRIC is valid: starts with (S,T,F,G,M), followed by 7 digits and one letter."""
    return re.match(r'^[STFGMstfgm]\d{7}[A-Za-z]$', nric)