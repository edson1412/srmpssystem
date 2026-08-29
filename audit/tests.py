"""
Tests for the audit trail system.
"""
from django.test import TestCase
from audit.models import AuditLog
from accounts.models import CustomUser
from prison.models import Region


class AuditLogTestCase(TestCase):
    """Test audit logging functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.region = Region.objects.create(name='Test Region')
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_audit_log_creation(self):
        """Test that audit logs can be created."""
        log = AuditLog.log_action(
            action='CREATE',
            user=self.user,
            content_object=self.region,
            description='Created test region'
        )
        
        self.assertEqual(log.action, 'CREATE')
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.model_name, 'Region')
        self.assertTrue(AuditLog.objects.filter(id=log.id).exists())
    
    def test_audit_log_immutability(self):
        """Test that audit logs cannot be edited or deleted."""
        log = AuditLog.log_action(
            action='CREATE',
            user=self.user,
            content_object=self.region,
            description='Test log'
        )
        
        # Verify it cannot be deleted
        self.assertFalse(log.can_be_deleted())
        self.assertFalse(log.can_be_edited())
    
    def test_get_client_ip(self):
        """Test IP address extraction."""
        from unittest.mock import Mock
        
        # Test with X-Forwarded-For header
        request = Mock()
        request.META = {'HTTP_X_FORWARDED_FOR': '192.168.1.1, 10.0.0.1'}
        
        ip = AuditLog.get_client_ip(request)
        self.assertEqual(ip, '192.168.1.1')
        
        # Test without X-Forwarded-For
        request.META = {'REMOTE_ADDR': '172.16.0.1'}
        ip = AuditLog.get_client_ip(request)
        self.assertEqual(ip, '172.16.0.1')
