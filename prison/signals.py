import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from .models import Notification

logger = logging.getLogger(__name__)


@receiver(m2m_changed, sender=Notification.target_users.through)
def email_notification_recipients(sender, instance, action, pk_set, **kwargs):
    """Email users as soon as they are assigned to an in-app notification."""
    if action != 'post_add' or not getattr(settings, 'EMAIL_NOTIFICATIONS_ENABLED', True):
        return

    recipients = instance.target_users.filter(
        pk__in=pk_set or set(),
        is_active=True,
    ).exclude(email='').values_list('email', flat=True)

    for email in recipients:
        try:
            send_mail(
                subject=instance.title,
                message=(
                    f"{instance.message}\n\n"
                    f"Priority: {instance.get_priority_display()}\n"
                    f"Open in Prison MS: {settings.SITE_URL}{instance.action_url or '/'}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception:
            logger.exception(
                'Could not email notification %s to %s', instance.pk, email
            )
