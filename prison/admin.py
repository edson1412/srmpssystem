# admin.py - Complete fixed version with no duplicates

from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.utils.html import format_html
from .models import *

# ============ CUSTOM FILTERS ============

class PrisonerClassFilter(SimpleListFilter):
    title = 'Prisoner Class'
    parameter_name = 'prisoner_class'

    def lookups(self, request, model_admin):
        return (
            ('convicted', 'Convicted'),
            ('remand', 'Remand'),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(prisoner_class=self.value())
        return queryset


class PrisonerNumberYearFilter(SimpleListFilter):
    title = 'Year'
    parameter_name = 'year'

    def lookups(self, request, model_admin):
        years = Prisoner.objects.dates('date_admitted', 'year')
        return [(str(year.year), str(year.year)) for year in years]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(date_admitted__year=self.value())
        return queryset


# ============ INLINES ============

class ConvictedPrisonerInline(admin.StackedInline):
    model = ConvictedPrisoner
    extra = 0
    classes = ('collapse',)

    def has_delete_permission(self, request, obj=None):
        return False


class RemandPrisonerInline(admin.StackedInline):
    model = RemandPrisoner
    extra = 0
    classes = ('collapse',)

    def has_delete_permission(self, request, obj=None):
        return False


class RiskAssessmentInline(admin.StackedInline):
    model = RiskAssessment
    extra = 0
    classes = ('collapse',)

    def has_delete_permission(self, request, obj=None):
        return False


class PrisonerParticularsInline(admin.StackedInline):
    model = PrisonerParticulars
    extra = 0
    classes = ('collapse',)

    def has_delete_permission(self, request, obj=None):
        return False


class PhysicalCharacteristicsInline(admin.StackedInline):
    model = PhysicalCharacteristics
    extra = 0
    classes = ('collapse',)

    def has_delete_permission(self, request, obj=None):
        return False


class RehabilitationProgramInline(admin.StackedInline):
    model = RehabilitationProgram
    extra = 0
    classes = ('collapse',)

    def has_delete_permission(self, request, obj=None):
        return False


class PrisonerTransferInline(admin.TabularInline):
    model = PrisonerTransfer
    extra = 0
    readonly_fields = ('transfer_date', 'transferred_by')
    classes = ('collapse',)

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class PrisonerItemInline(admin.TabularInline):
    model = PrisonerItem
    extra = 0
    fields = ('item_type', 'description', 'quantity', 'initial_amount', 'current_amount', 'currency', 'date_received', 'is_collected')
    readonly_fields = ('current_amount', 'received_by', 'created_at', 'updated_at')
    classes = ('collapse',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('prisoner')

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


class PrisonerItemTransactionInline(admin.TabularInline):
    model = PrisonerItemTransaction
    extra = 0
    fields = ('item', 'transaction_type', 'amount', 'reason', 'transaction_date', 'transacted_by')
    readonly_fields = ('transaction_date', 'transacted_by')
    classes = ('collapse',)

    def get_queryset(self, request):
        if hasattr(self, 'parent_object') and self.parent_object:
            return super().get_queryset(request).filter(item__prisoner=self.parent_object)
        return super().get_queryset(request).none()

    def has_add_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False


class PrisonerAuditHistoryInline(admin.TabularInline):
    model = PrisonerAuditHistory
    extra = 0
    readonly_fields = ('changed_by', 'field_name', 'old_value', 'new_value', 'change_reason', 'changed_at', 'ip_address')
    can_delete = False
    classes = ('collapse',)
    fields = ('field_name', 'old_value', 'new_value', 'change_reason', 'changed_at')

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ReleaseAuditLogInline(admin.TabularInline):
    model = ReleaseAuditLog
    extra = 0
    readonly_fields = ('action', 'performed_by', 'original_release_date', 'modified_release_date',
                       'original_sentence', 'modified_sentence', 'review_role', 'approval_status',
                       'change_reason', 'performed_at', 'ip_address')
    can_delete = False
    classes = ('collapse',)
    fields = ('action', 'original_release_date', 'modified_release_date', 'approval_status', 'performed_at')

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class SentryAlertInline(admin.TabularInline):
    model = SentryAlert
    extra = 0
    readonly_fields = ('alert_type', 'severity', 'title', 'detected_at', 'is_resolved')
    can_delete = False
    classes = ('collapse',)
    fields = ('alert_type', 'severity', 'title', 'is_resolved', 'detected_at')

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ============ PRISONER NUMBER COUNTER ADMIN ============

@admin.register(PrisonerNumberCounter)
class PrisonerNumberCounterAdmin(admin.ModelAdmin):
    list_display = (
        'prison_station',
        'prisoner_class_display',
        'year',
        'last_number',
        'formatted_number',
        'updated_at'
    )
    list_filter = ('prison_station', 'prisoner_class', 'year')
    search_fields = ('prison_station__name', 'prison_station__code')
    readonly_fields = ('created_at', 'updated_at', 'formatted_number')
    fields = ('prison_station', 'prisoner_class', 'year', 'last_number', 'formatted_number', 'created_at', 'updated_at')

    def prisoner_class_display(self, obj):
        return obj.get_prisoner_class_display()
    prisoner_class_display.short_description = 'Class'
    prisoner_class_display.admin_order_field = 'prisoner_class'

    def formatted_number(self, obj):
        station_code = obj.prison_station.code.upper()
        num_str = str(obj.last_number).zfill(3)
        if obj.prisoner_class == 'convicted':
            return f"{station_code}{num_str}/{obj.year}"
        else:
            return f"{station_code}-R{num_str}/{obj.year}"
    formatted_number.short_description = 'Latest Number'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('prison_station', 'prisoner_class', 'year')
        return self.readonly_fields

    actions = ['reset_counter']

    def reset_counter(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(request, "Only superusers can reset counters.", level='error')
            return

        count = 0
        for counter in queryset:
            old_number = counter.last_number
            counter.last_number = 0
            counter.save(update_fields=['last_number', 'updated_at'])
            count += 1

        self.message_user(
            request,
            f"Successfully reset {count} counter(s).",
            level='success'
        )
    reset_counter.short_description = "Reset selected counters to 0"


# ============ PRISONER ADMIN ============

@admin.register(Prisoner)
class PrisonerAdmin(admin.ModelAdmin):
    list_display = (
        'prisoner_number',
        'full_name',
        'prisoner_class',
        'prison_station',
        'date_admitted',
        'is_active',
        'has_fingerprint_display'
    )
    list_filter = (
        PrisonerClassFilter,
        'prison_station',
        'is_active',
        'date_admitted',
        'sex',
        PrisonerNumberYearFilter,
    )
    search_fields = (
        'prisoner_number',
        'first_name',
        'middle_name',
        'surname',
        'prison_station__name',
        'prison_station__code'
    )
    readonly_fields = (
        'prisoner_number',
        'last_modified',
        'fingerprint_hash',
        'is_identity_verified',
        'identity_verified_at',
        'is_recidivist',
        'recidivism_detected_at',
        'recidivism_detected_by',
        'previous_prisoner_numbers'
    )
    fieldsets = (
        ('Prisoner Information', {
            'fields': (
                'prisoner_number',
                ('first_name', 'middle_name', 'surname'),
                ('sex', 'age'),
                ('prisoner_class', 'prison_station'),
                ('block_number', 'cell_number'),
                'date_admitted',
                'is_active',
                'date_released',
                'image',
                'document'
            )
        }),
        ('Biometric Information', {
            'fields': (
                'has_fingerprint_display',
                'fingerprint_quality',
                'fingerprint_captured_at',
                'fingerprint_captured_by',
                'fingerprint_device',
                'is_identity_verified',
                'identity_verified_at',
                'identity_verified_by',
                'identity_verification_notes',
            ),
            'classes': ('collapse',)
        }),
        ('Recidivism Tracking', {
            'fields': (
                'is_recidivist',
                'previous_prisoner_numbers',
                'first_incarceration_date',
                'recidivism_detected_at',
                'recidivism_detected_by',
                'recidivism_notes',
            ),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': (
                'created_by',
                'last_modified',
            ),
            'classes': ('collapse',)
        }),
    )

    inlines = [
        ConvictedPrisonerInline,
        RemandPrisonerInline,
        RiskAssessmentInline,
        PrisonerParticularsInline,
        PhysicalCharacteristicsInline,
        RehabilitationProgramInline,
        PrisonerTransferInline,
        PrisonerItemInline,
        PrisonerAuditHistoryInline,
        ReleaseAuditLogInline,
        SentryAlertInline,
    ]

    def has_fingerprint_display(self, obj):
        if obj.has_fingerprint:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Captured</span>'
            )
        return format_html(
            '<span style="color: #dc2626;">✗ Not Captured</span>'
        )
    has_fingerprint_display.short_description = 'Fingerprint Status'

    def get_inline_instances(self, request, obj=None):
        inlines = []
        if obj is None:
            return inlines

        base_inlines = [
            PrisonerParticularsInline,
            PhysicalCharacteristicsInline,
            PrisonerItemInline,
            PrisonerAuditHistoryInline,
            ReleaseAuditLogInline,
            SentryAlertInline,
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
            if hasattr(inline, 'parent_object'):
                inline.parent_object = obj
            inlines.append(inline)

        return inlines

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.is_superuser:
            if 'delete_selected' in actions:
                del actions['delete_selected']
        return actions


# ============ PRISON STATION ADMIN ============

@admin.register(PrisonStation)
class PrisonStationAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'location', 'region_display', 'capacity', 'prisoner_count', 'date_established')
    list_filter = ('region',)
    search_fields = ('name', 'code', 'location')
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Station Information', {
            'fields': (
                ('name', 'code'),
                ('location', 'region'),
                ('capacity', 'date_established'),
            )
        }),
        ('System Information', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    def region_display(self, obj):
        return obj.get_region_display()
    region_display.short_description = 'Region'
    region_display.admin_order_field = 'region'

    def prisoner_count(self, obj):
        count = Prisoner.objects.filter(prison_station=obj, is_active=True).count()
        return format_html(
            '<span style="font-weight: bold; color: #0ea5e9;">{}</span>',
            count
        )
    prisoner_count.short_description = 'Active Prisoners'

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ============ ACTIVITY LOG ADMIN ============

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'model', 'object_id', 'timestamp')
    list_filter = ('action', 'model', 'timestamp')
    search_fields = ('user__username', 'details')
    readonly_fields = ('user', 'action', 'model', 'object_id', 'details', 'timestamp')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# ============ RELEASE ON REMISSION ADMIN ============

@admin.register(ReleaseOnRemission)
class ReleaseOnRemissionAdmin(admin.ModelAdmin):
    list_display = ('prisoner', 'release_date', 'original_sentence', 'remission_months', 'reduction_months')
    list_filter = ('release_date',)
    search_fields = ('prisoner__prisoner_number', 'prisoner__first_name', 'prisoner__surname')
    readonly_fields = ('processed_date',)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ============ PRISONER ITEM ADMIN ============

@admin.register(PrisonerItem)
class PrisonerItemAdmin(admin.ModelAdmin):
    list_display = (
        'prisoner',
        'item_type',
        'description',
        'quantity',
        'current_amount_display',
        'currency',
        'date_received',
        'is_collected'
    )
    list_filter = ('item_type', 'currency', 'date_received', 'prisoner__prison_station', 'is_collected')
    search_fields = ('prisoner__prisoner_number', 'prisoner__first_name', 'prisoner__surname', 'description')
    raw_id_fields = ('prisoner', 'received_by')
    readonly_fields = ('current_amount', 'created_at', 'updated_at')
    inlines = [PrisonerItemTransactionInline]
    fieldsets = (
        ('Item Information', {
            'fields': (
                'prisoner',
                ('item_type', 'description'),
                ('quantity', 'currency'),
                ('initial_amount', 'current_amount'),
                'date_received',
                'received_by',
                'notes',
                'is_collected',
            )
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def current_amount_display(self, obj):
        if obj.item_type == 'money':
            return format_html(
                '<span style="font-weight: bold; color: #0ea5e9;">{:.2f}</span>',
                obj.current_amount
            )
        return '—'
    current_amount_display.short_description = 'Current Amount'

    def save_model(self, request, obj, form, change):
        if not obj.received_by:
            obj.received_by = request.user
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('prisoner', 'item_type', 'initial_amount')
        return self.readonly_fields


# ============ PRISONER ITEM TRANSACTION ADMIN ============

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

    def has_delete_permission(self, request, obj=None):
        return False


# ============ RATION MANAGEMENT ADMIN ============

@admin.register(RationItem)
class RationItemAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'prison_station',
        'current_stock_kg',
        'unit',
        'low_stock_threshold_kg',
        'is_low_stock_display',
        'estimated_days_remaining',
        'is_active'
    )
    list_filter = ('prison_station', 'is_active', 'unit')
    search_fields = ('name', 'prison_station__name')
    readonly_fields = ('current_stock_kg', 'estimated_days_remaining', 'last_stock_update', 'last_consumption_date')
    fieldsets = (
        ('Item Information', {
            'fields': (
                ('name', 'unit'),
                ('prison_station', 'is_active'),
                'current_stock_kg',
                ('low_stock_threshold_kg', 'daily_consumption_per_prisoner_kg'),
                'estimated_days_remaining',
            )
        }),
        ('System Information', {
            'fields': ('last_stock_update', 'last_consumption_date', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def is_low_stock_display(self, obj):
        if obj.is_low_stock:
            return format_html(
                '<span style="color: #dc2626; font-weight: bold;">⚠ Low Stock</span>'
            )
        return format_html(
            '<span style="color: #16a34a;">✓ Adequate</span>'
        )
    is_low_stock_display.short_description = 'Stock Status'

    def save_model(self, request, obj, form, change):
        obj.save()
        obj.update_estimated_days()


@admin.register(RationConsumption)
class RationConsumptionAdmin(admin.ModelAdmin):
    list_display = ('item', 'consumption_date', 'quantity_used_kg', 'num_prisoners_fed', 'consumed_by', 'is_auto_calculated')
    list_filter = ('item__prison_station', 'consumption_date', 'item', 'is_auto_calculated')
    search_fields = ('item__name', 'notes')
    readonly_fields = ('created_at',)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RationProcurement)
class RationProcurementAdmin(admin.ModelAdmin):
    list_display = ('item', 'procurement_date', 'quantity_procured_kg', 'supplier', 'procured_by')
    list_filter = ('item__prison_station', 'procurement_date', 'item')
    search_fields = ('item__name', 'supplier', 'invoice_number')
    readonly_fields = ('created_at',)

    def save_model(self, request, obj, form, change):
        if not obj.procured_by:
            obj.procured_by = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False


# ============ VISITOR ADMIN ============

@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'prisoner', 'relationship', 'visit_date', 'visit_time', 'is_approved')
    list_filter = ('is_approved', 'relationship', 'visit_date')
    search_fields = ('first_name', 'surname', 'prisoner__prisoner_number', 'prisoner__first_name', 'prisoner__surname')
    readonly_fields = ('created_at', 'last_updated')
    fieldsets = (
        ('Visitor Information', {
            'fields': (
                ('first_name', 'surname'),
                ('id_number', 'contact_number'),
                'address',
                ('relationship', 'purpose_of_visit'),
            )
        }),
        ('Visit Details', {
            'fields': (
                'prisoner',
                ('visit_date', 'visit_time'),
                'location',
                'items',
            )
        }),
        ('Approval Status', {
            'fields': (
                'is_approved',
                'approved_by',
                'denial_reason',
            )
        }),
        ('System Information', {
            'fields': ('created_by', 'created_at', 'last_updated'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ============ MEDICAL RECORD ADMIN ============

@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ('prisoner', 'record_date', 'category', 'diagnosis', 'next_checkup', 'is_upcoming_display')
    list_filter = ('category', 'record_date', 'next_checkup')
    search_fields = ('prisoner__prisoner_number', 'prisoner__first_name', 'prisoner__surname', 'diagnosis')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Medical Record', {
            'fields': (
                'prisoner',
                ('record_date', 'category'),
                'diagnosis',
                'treatment',
                'prescribed_medication',
                'next_checkup',
                'recorded_by',
                'notes',
            )
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def is_upcoming_display(self, obj):
        if obj.next_checkup:
            days_until = (obj.next_checkup - timezone.now().date()).days
            if days_until < 0:
                return format_html('<span style="color: #dc2626;">⚠ Overdue</span>')
            elif days_until <= 7:
                return format_html('<span style="color: #d97706;">⏳ {} days</span>', days_until)
            return format_html('<span style="color: #16a34a;">✓ {} days</span>', days_until)
        return '—'
    is_upcoming_display.short_description = 'Checkup Status'

    def save_model(self, request, obj, form, change):
        if not obj.recorded_by:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)


# ============ INCIDENT REPORT ADMIN ============

@admin.register(IncidentReport)
class IncidentReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'severity', 'date_occurred', 'location', 'reported_by', 'follow_up_required')
    list_filter = ('severity', 'date_occurred', 'follow_up_required')
    search_fields = ('title', 'description', 'location')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('involved_prisoners',)
    fieldsets = (
        ('Incident Details', {
            'fields': (
                'title',
                'description',
                ('severity', 'date_occurred'),
                'location',
                'involved_prisoners',
                'involved_staff',
            )
        }),
        ('Actions & Follow-up', {
            'fields': (
                'actions_taken',
                ('follow_up_required', 'follow_up_notes'),
            )
        }),
        ('System Information', {
            'fields': ('reported_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.reported_by:
            obj.reported_by = request.user
        super().save_model(request, obj, form, change)


# ============ FINGERPRINT / BIOMETRIC ADMIN ============

@admin.register(FingerprintDevice)
class FingerprintDeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'device_type', 'serial_number', 'status', 'prison_station', 'last_used_at')
    list_filter = ('status', 'device_type', 'prison_station')
    search_fields = ('name', 'serial_number', 'prison_station__name')
    fieldsets = (
        ('Device Information', {
            'fields': (
                ('name', 'device_type'),
                'serial_number',
                ('status', 'prison_station'),
                'notes',
            )
        }),
        ('System Information', {
            'fields': ('last_used_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(FingerprintMatch)
class FingerprintMatchAdmin(admin.ModelAdmin):
    list_display = ('searched_prisoner', 'matched_prisoner', 'match_score', 'match_status', 'search_timestamp', 'searched_by')
    list_filter = ('match_status', 'search_timestamp')
    search_fields = ('searched_prisoner__prisoner_number', 'matched_prisoner__prisoner_number')
    readonly_fields = ('search_timestamp',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(FingerprintAuditLog)
class FingerprintAuditLogAdmin(admin.ModelAdmin):
    list_display = ('prisoner', 'operation', 'performed_by', 'performed_at', 'success')
    list_filter = ('operation', 'success', 'performed_at')
    search_fields = ('prisoner__prisoner_number', 'prisoner__first_name', 'prisoner__surname')
    readonly_fields = ('performed_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# ============ NOTIFICATION ADMIN ============

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'notification_type', 'priority', 'is_read', 'created_at', 'expires_at')
    list_filter = ('notification_type', 'priority', 'is_read', 'created_at')
    search_fields = ('title', 'message')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('target_users',)

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser


# ============ PRISONER RELEASE REVIEW ADMIN ============
# FIX: Only ONE registration for PrisonerReleaseReview

@admin.register(PrisonerReleaseReview)
class PrisonerReleaseReviewAdmin(admin.ModelAdmin):
    list_display = ('prisoner', 'review_role', 'status', 'requested_by', 'release_date', 'requested_at', 'reviewed_at')
    list_filter = ('status', 'review_role', 'release_date')
    search_fields = ('prisoner__prisoner_number', 'prisoner__first_name', 'prisoner__surname')
    readonly_fields = ('requested_at', 'reviewed_at')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ============ AUDIT TRAIL ADMIN ============

@admin.register(AuditTrail)
class AuditTrailAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'model_name', 'object_repr', 'severity', 'ip_address')
    list_filter = ('action', 'severity', 'model_name', 'timestamp', 'user')
    search_fields = ('user__username', 'object_repr', 'description', 'ip_address')
    readonly_fields = ('timestamp', 'user', 'action', 'model_name', 'object_id', 'object_repr',
                       'changes', 'old_values', 'new_values', 'ip_address', 'user_agent',
                       'severity', 'prison_station', 'description', 'request_path', 'session_id')
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PrisonerAuditHistory)
class PrisonerAuditHistoryAdmin(admin.ModelAdmin):
    list_display = ('prisoner', 'changed_by', 'field_name', 'changed_at', 'ip_address')
    list_filter = ('field_name', 'changed_at', 'changed_by')
    search_fields = ('prisoner__prisoner_number', 'prisoner__first_name', 'prisoner__surname', 'field_name')
    readonly_fields = ('prisoner', 'changed_by', 'field_name', 'old_value', 'new_value',
                       'change_reason', 'changed_at', 'ip_address')
    date_hierarchy = 'changed_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReleaseAuditLog)
class ReleaseAuditLogAdmin(admin.ModelAdmin):
    list_display = ('prisoner', 'action', 'performed_by', 'performed_at', 'approval_status', 'ip_address')
    list_filter = ('action', 'approval_status', 'performed_at', 'performed_by')
    search_fields = ('prisoner__prisoner_number', 'prisoner__first_name', 'prisoner__surname')
    readonly_fields = ('prisoner', 'action', 'performed_by', 'original_release_date', 'modified_release_date',
                       'original_sentence', 'modified_sentence', 'review_role', 'approval_status',
                       'change_reason', 'risk_flags', 'performed_at', 'ip_address')
    date_hierarchy = 'performed_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SentryAlert)
class SentryAlertAdmin(admin.ModelAdmin):
    list_display = ('title', 'alert_type', 'severity', 'is_resolved', 'detected_at', 'resolved_at')
    list_filter = ('alert_type', 'severity', 'is_resolved', 'detected_at')
    search_fields = ('title', 'description', 'prisoner__prisoner_number')
    readonly_fields = ('alert_type', 'severity', 'title', 'description', 'prisoner', 'user',
                       'audit_trail', 'detected_at', 'ip_address')
    list_editable = ('is_resolved',)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if obj.is_resolved and not obj.resolved_by:
            obj.resolved_by = request.user
            obj.resolved_at = timezone.now()
        super().save_model(request, obj, form, change)