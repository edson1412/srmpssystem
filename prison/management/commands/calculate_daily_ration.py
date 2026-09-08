from django.core.management.base import BaseCommand
from django.utils import timezone
from prison.models import RationItem, Prisoner
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Calculate and record daily ration consumption for all active ration items'

    def handle(self, *args, **options):
        self.stdout.write('Starting daily ration consumption calculation...')
        
        # Get all active ration items
        ration_items = RationItem.objects.filter(is_active=True)
        
        total_items_processed = 0
        total_consumption_records = 0
        
        for item in ration_items:
            try:
                # Get current prisoner count for this station
                prisoner_count = Prisoner.objects.filter(
                    prison_station=item.prison_station,
                    is_active=True
                ).count()
                
                if prisoner_count == 0:
                    self.stdout.write(f'Skipping {item.name} - no prisoners at {item.prison_station.name}')
                    continue
                
                # Calculate daily consumption
                daily_consumption = item.daily_consumption_per_prisoner_kg * prisoner_count
                
                if daily_consumption <= 0:
                    self.stdout.write(f'Skipping {item.name} - daily consumption rate is 0')
                    continue
                
                # Check if consumption already recorded for today
                from prison.models import RationConsumption
                existing = RationConsumption.objects.filter(
                    item=item,
                    consumption_date=timezone.now().date()
                ).first()
                
                if existing:
                    self.stdout.write(f'Consumption already recorded for {item.name} today')
                    continue
                
                # Create consumption record
                consumption = RationConsumption.objects.create(
                    item=item,
                    consumption_date=timezone.now().date(),
                    quantity_used_kg=daily_consumption,
                    num_prisoners_fed=prisoner_count,
                    is_auto_calculated=True,
                    notes=f"Auto-calculated based on {prisoner_count} prisoners"
                )
                
                # Update stock
                item.current_stock_kg -= daily_consumption
                item.last_consumption_date = timezone.now().date()
                item.save(update_fields=['current_stock_kg', 'last_consumption_date', 'last_stock_update'])
                
                # Update estimated days
                item.update_estimated_days()
                
                total_consumption_records += 1
                self.stdout.write(f'✓ Recorded {daily_consumption:.3f}kg consumption for {item.name} ({prisoner_count} prisoners)')
                
            except Exception as e:
                self.stdout.write(f'✗ Error processing {item.name}: {str(e)}')
        
        total_items_processed = ration_items.count()
        
        self.stdout.write(self.style.SUCCESS(
            f'Completed: {total_consumption_records} consumption records created from {total_items_processed} ration items'
        ))