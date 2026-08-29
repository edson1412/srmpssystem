from django.contrib import admin
from .models import *

class ConvictedPrisonerInline(admin.StackedInline):
    model = ConvictedPrisoner
    extra = 0

class RemandPrisonerInline(admin.StackedInline):
    model = RemandPrisoner
    extra = 0

class RiskAssessmentInline(admin.StackedInline):
    model = RiskAssessment
    extra = 0

class PrisonerParticularsInline(admin.StackedInline):
    model = PrisonerParticulars
    extra = 0

class PhysicalCharacteristicsInline(admin.StackedInline):
    model = PhysicalCharacteristics
    extra = 0

class RehabilitationProgramInline(admin.StackedInline):
    model = RehabilitationProgram
    extra = 0

class PrisonerTransferInline(admin.TabularInline):
    model = PrisonerTransfer
    extra = 0
    readonly_fields = ('transfer_date', 'transferred_by')

    def has_add_permission(self, request, obj=None):
        return False

# New Inlines for PrisonerItem and PrisonerItemTransaction
class PrisonerItemInline(admin.TabularInline):
    model = PrisonerItem
    extra = 0
    fields = ('item_type', 'description', 'quantity', 'initial_amount', 'current_amount', 'currency', 'date_received', 'received_by')
    readonly_fields = ('current_amount', 'received_by') # current_amount updated by transactions, received_by set automatically

    def get_queryset(self, request):
        # Only show money items for the current prisoner in this inline
        return super().get_queryset(request)

    def has_change_permission(self, request, obj=None):
        # Allow changing for all fields except current_amount and received_by
        return True

    def has_add_permission(self, request, obj=None):
        return True # Allow adding new items directly from prisoner admin

class PrisonerItemTransactionInline(admin.TabularInline):
    model = PrisonerItemTransaction
    extra = 0
    fields = ('item', 'transaction_type', 'amount', 'reason', 'transaction_date', 'transacted_by')
    readonly_fields = ('transaction_date', 'transacted_by')

    def get_queryset(self, request):
        # Filter transactions to only show for the current prisoner's items
        if self.parent_object:
            return super().get_queryset(request).filter(item__prisoner=self.parent_object)
        return super().get_queryset(request).none()

    def has_add_permission(self, request, obj=None):
        return True # Allow adding transactions directly from prisoner admin

@admin.register(Prisoner)
class PrisonerAdmin(admin.ModelAdmin):
    list_display = ('prisoner_number', 'full_name', 'prisoner_class', 'prison_station', 'date_admitted', 'is_active')
    list_filter = ('prisoner_class', 'prison_station', 'is_active', 'date_admitted')
    search_fields = ('prisoner_number', 'first_name', 'middle_name', 'surname')
    inlines = [
        ConvictedPrisonerInline,
        RemandPrisonerInline,
        RiskAssessmentInline,
        PrisonerParticularsInline,
        PhysicalCharacteristicsInline,
        RehabilitationProgramInline,
        PrisonerTransferInline,
        PrisonerItemInline, # Add PrisonerItemInline here
    ]

    def get_inline_instances(self, request, obj=None):
        # Only show relevant inlines based on prisoner class
        inlines = []
        if obj is None:
            return inlines

        base_inlines = [
            PrisonerParticularsInline,
            PhysicalCharacteristicsInline,
            PrisonerItemInline, # Keep PrisonerItemInline for all prisoners
        ]

        if obj.prisoner_class == 'convicted':
            base_inlines.extend([
                ConvictedPrisonerInline,
                RiskAssessmentInline,
                RehabilitationProgramInline,
            ])
        else:
            base_inlines.append(RemandPrisonerInline)

        base_inlines.append(PrisonerTransferInline)

        for inline_class in base_inlines:
            inline = inline_class(self.model, self.admin_site)
            # Set parent_object for inlines that need it for filtering (like PrisonerItemTransactionInline)
            if hasattr(inline, 'parent_object'):
                inline.parent_object = obj
            inlines.append(inline)

        return inlines

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'model', 'object_id', 'timestamp')
    list_filter = ('action', 'model', 'timestamp')
    search_fields = ('user__username', 'details')
    readonly_fields = ('user', 'action', 'model', 'object_id', 'details', 'timestamp')

    def has_add_permission(self, request):
        return False

@admin.register(ReleaseOnRemission)
class ReleaseOnRemissionAdmin(admin.ModelAdmin):
    list_display = ('prisoner', 'release_date', 'original_sentence', 'remission_months', 'reduction_months')
    list_filter = ('release_date',)
    search_fields = ('prisoner__prisoner_number', 'prisoner__first_name', 'prisoner__surname')
    readonly_fields = ('processed_date',)

# Register new models
@admin.register(PrisonerItem)
class PrisonerItemAdmin(admin.ModelAdmin):
    list_display = ('prisoner', 'item_type', 'description', 'quantity', 'initial_amount', 'current_amount', 'currency', 'date_received', 'received_by')
    list_filter = ('item_type', 'currency', 'date_received', 'prisoner__prison_station')
    search_fields = ('prisoner__prisoner_number', 'prisoner__first_name', 'prisoner__surname', 'description')
    raw_id_fields = ('prisoner', 'received_by') # Use raw_id_fields for FKs to improve performance
    readonly_fields = ('current_amount', 'created_at', 'updated_at') # current_amount is managed by transactions
    inlines = [PrisonerItemTransactionInline] # Show transactions directly under item

    def save_model(self, request, obj, form, change):
        if not obj.received_by:
            obj.received_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(PrisonerItemTransaction)
class PrisonerItemTransactionAdmin(admin.ModelAdmin):
    list_display = ('item_display', 'prisoner_display', 'transaction_type', 'amount', 'transaction_date', 'transacted_by')
    list_filter = ('transaction_type', 'transaction_date', 'item__item_type', 'item__prisoner__prison_station')
    search_fields = ('item__prisoner__prisoner_number', 'item__prisoner__first_name', 'item__prisoner__surname', 'reason')
    raw_id_fields = ('item', 'transacted_by')
    readonly_fields = ('transaction_date', 'transacted_by')

    def item_display(self, obj):
        return f"{obj.item.description} ({obj.item.get_item_type_display()})"
    item_display.short_description = "Item"

    def prisoner_display(self, obj):
        return obj.item.prisoner.full_name
    prisoner_display.short_description = "Prisoner"

    def save_model(self, request, obj, form, change):
        if not obj.transacted_by:
            obj.transacted_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(RationItem)
class RationItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'prison_station', 'current_stock_kg', 'unit', 'low_stock_threshold_kg', 'is_active')
    list_filter = ('prison_station', 'is_active', 'unit')
    search_fields = ('name',)

@admin.register(RationConsumption)
class RationConsumptionAdmin(admin.ModelAdmin):
    list_display = ('item', 'consumption_date', 'quantity_used_kg', 'num_prisoners_fed', 'consumed_by')
    list_filter = ('item__prison_station', 'consumption_date', 'item')
    search_fields = ('item__name', 'notes')
    readonly_fields = ('created_at',)

@admin.register(RationProcurement)
class RationProcurementAdmin(admin.ModelAdmin):
    list_display = ('item', 'procurement_date', 'quantity_procured_kg', 'supplier', 'procured_by')
    list_filter = ('item__prison_station', 'procurement_date', 'item')
    search_fields = ('item__name', 'supplier', 'invoice_number')
    readonly_fields = ('created_at',)

