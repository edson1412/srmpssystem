# hrms/context_processors.py

def user_roles(request):
    """
    Adds user role and permission flags to the context for all templates.
    """
    user = request.user
    if user.is_authenticated:
        return {
            'is_national_level': user.is_national_level,
            'is_regional_level': user.is_regional_level,
            'is_station_level': user.is_station_level,
            'is_commissioner': user.is_commissioner,
            'is_national_hr': user.is_national_hr,
            'is_rco': user.is_rco,
            'is_rho': user.is_rho,
            'is_oc': user.is_oc,
            'is_so': user.is_so,
            'is_station_hr': user.is_station_hr,
            'is_training_wing_officer': user.is_training_wing_officer,
            'is_commissioner_training_school': user.is_commissioner_training_school,
            'is_ict_personnel': user.is_ict_personnel,
            'can_access_training': user.can_access_training,
        }
    return {}
