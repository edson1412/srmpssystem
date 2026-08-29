"""Role based routing for the single sign-in page.

Both modules (inmate management in ``prison`` and officer management in ``hrms``)
are served by one login page; the landing page depends on the user's role.
"""

from django.urls import reverse

from .models import CustomUser

# Landing url name per role. Names without a namespace belong to the prison app.
ROLE_LANDING_URLS = {
    # Prison/Inmate Management Roles
    CustomUser.ROLE_SUPERUSER: 'dashboard',
    CustomUser.ROLE_ADMIN: 'dashboard',
    CustomUser.ROLE_RECEPTION: 'release_hub',
    CustomUser.ROLE_OFFICER_IN_CHARGE: 'hrms:dashboard',  # Dual access - prioritize HRMS
    CustomUser.ROLE_STATION_OFFICER: 'release_hub',
    CustomUser.ROLE_VISITOR_ATTENDANT: 'visitor_list',
    CustomUser.ROLE_MEDICAL: 'medical_record_list',
    
    # HRMS/Officer Management Roles
    CustomUser.ROLE_NATIONAL_COMMISSIONER: 'hrms:dashboard',
    CustomUser.ROLE_NATIONAL_HR: 'hrms:dashboard',
    CustomUser.ROLE_REGIONAL_COMMANDING_OFFICER: 'hrms:dashboard',
    CustomUser.ROLE_REGIONAL_HEADQUARTERS_OFFICER: 'hrms:dashboard',
    CustomUser.ROLE_REGIONAL_HR: 'hrms:dashboard',
    CustomUser.ROLE_STATION_HR: 'hrms:dashboard',
    CustomUser.ROLE_TRAINING_WING_OFFICER: 'hrms:training_dashboard',
    CustomUser.ROLE_COMMISSIONER_TRAINING_SCHOOL: 'hrms:training_dashboard',
    CustomUser.ROLE_ICT_PERSONNEL: 'hrms:ict_dashboard',
}

DEFAULT_PRISON_LANDING_URL_NAME = 'dashboard'
DEFAULT_HRMS_LANDING_URL_NAME = 'hrms:dashboard'


def landing_url_name_for(user):
    """Determine the appropriate landing URL name based on user role."""
    if user.is_superuser:
        return ROLE_LANDING_URLS[CustomUser.ROLE_SUPERUSER]
    
    # First check if there's a specific mapping for this role
    if user.role in ROLE_LANDING_URLS:
        return ROLE_LANDING_URLS[user.role]
    
    # Fallback logic based on role categories
    # Prioritize HRMS for dual access users since it's typically their primary function
    if user.role in CustomUser.HRMS_ROLES:
        return DEFAULT_HRMS_LANDING_URL_NAME
    elif user.role in CustomUser.PRISON_ROLES:
        return DEFAULT_PRISON_LANDING_URL_NAME
    else:
        # Ultimate fallback to prison dashboard
        return DEFAULT_PRISON_LANDING_URL_NAME


def landing_url_for(user):
    """Absolute path the user should land on right after signing in.
    
    For users with dual dashboard access, redirects to dashboard choice page.
    For single dashboard users, redirects to their primary dashboard.
    """
    # Check if user has dual access to dashboards
    if user.has_dual_dashboards():
        return reverse('dashboard_choice')
    
    return reverse(landing_url_name_for(user))
