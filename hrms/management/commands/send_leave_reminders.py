from django.core.management.base import BaseCommand
from django.utils import timezone
from hrms.email_utils import send_leave_reminder_email
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Send reminder emails to officers whose leave ends in 3 days'

    def handle(self, *args, **options):
        """
        Execute the command to send leave reminder emails.
        This command is intended to be run daily via a scheduled task (cron job).
        """
        self.stdout.write("Starting to send leave reminder emails...")
        
        try:
            result = send_leave_reminder_email()
            
            success_count = result['success_count']
            failure_count = result['failure_count']
            total_processed = result['total_processed']
            
            if total_processed > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully processed {total_processed} leave reminders. "
                        f"Sent: {success_count}, Failed: {failure_count}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "No officers with leave ending in 3 days found."
                    )
                )
                
            if failure_count > 0:
                self.stdout.write(
                    self.style.ERROR(
                        f"Failed to send {failure_count} reminder emails. Check logs for details."
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"Error occurred while sending leave reminders: {str(e)}"
                )
            )
            logger.error(f"Error in send_leave_reminders command: {str(e)}")
            return 1
            
        self.stdout.write("Leave reminder email sending completed.")
        return 0
