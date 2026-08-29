"""
Custom password validators for the Prison HRMS application.
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
import re


class LetterAndNumberValidator:
    """
    Validates that the password contains at least one letter and one number.
    """
    def validate(self, password, user=None):
        has_letter = re.search(r'[a-zA-Z]', password)
        has_number = re.search(r'[0-9]', password)
        
        if not has_letter or not has_number:
            raise ValidationError(
                _("Password must contain at least one letter and one number."),
                code='no_letter_or_number',
            )
    
    def get_help_text(self):
        return _("Password must contain at least one letter and one number.")
