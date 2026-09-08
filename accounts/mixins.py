from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import UserPassesTestMixin

class RoleRequiredMixin(UserPassesTestMixin):
    roles_required = []

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False

        # Super admins can do anything
        if user.is_super_admin():
            return True

        # Check if user has one of the required roles
        for role in self.roles_required:
            if hasattr(user, f'is_{role}') and getattr(user, f'is_{role}')():
                return True

        return False

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("You don't have permission to access this page.")
        return super().handle_no_permission()


class ICTAccessMixin(UserPassesTestMixin):
    """Mixin for ICT Personnel specific access"""

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False

        # ICT Personnel and Super Admins can access
        return user.is_ict_personnel() or user.is_super_admin()

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("Only ICT Personnel can access this page.")
        return super().handle_no_permission()