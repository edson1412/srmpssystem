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

# Inlines for PrisonerItem and PrisonerItemTransaction
class PrisonerItemInline(admin.TabularInline):
    model = PrisonerItem
    extra = 0
    fields = ('item_type', 'description', 'quantity', 'initial_amount', 'current_amount', 'currency', 'date_received', 'received_by')
    readonly_fields = ('current_amount', 'received_by')

    def has_change_permission(self, request, obj=None):
        return True

    def has_add_permission(self, request, obj=None):
        return True

class PrisonerItemTransactionInline(admin.TabularInline):
    model = PrisonerItemTransaction
    extra = 0
    fields = ('item', 'transaction_type', 'amount', 'reason', 'transaction_date', 'transacted_by')
    readonly_fields = ('transaction_date', 'transacted_by')

    def get_queryset(self, request):
        if hasattr(self, 'parent_object') and self.parent_object:
            return super().get_queryset(request).filter(item__prisoner=self.parent_object)
        return super().get_queryset(request).none()

    def has_add_permission(self, request, obj=None):
        return True


class InmateReturnDataInline(admin.TabularInline):
    """Inline for InmateReturnData"""
    model = InmateReturnData
    extra = 0
    fields = (
        'row_number', 'serial_no', 'prisoner_number', 'full_name', 
        'sex', 'age', 'offense', 'court', 'sentence_months'
    )
    # Remove 'created_at' and 'updated_at' from readonly_fields since they may not exist
    readonly_fields = ('row_number',)
    can_delete = True
    show_change_link = True
    ordering = ('row_number', 'serial_no')
    
    def has_add_permission(self, request, obj=None):
        return True
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('row_number', 'serial_no')


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
        PrisonerItemInline,
    ]

    def get_inline_instances(self, request, obj=None):
        inlines = []
        if obj is None:
            return inlines

        base_inlines = [
            PrisonerParticularsInline,
            PhysicalCharacteristicsInline,
            PrisonerItemInline,
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


@admin.register(PrisonerItem)
class PrisonerItemAdmin(admin.ModelAdmin):
    list_display = ('prisoner', 'item_type', 'description', 'quantity', 'initial_amount', 'current_amount', 'currency', 'date_received', 'received_by')
    list_filter = ('item_type', 'currency', 'date_received', 'prisoner__prison_station')
    search_fields = ('prisoner__prisoner_number', 'prisoner__first_name', 'prisoner__surname', 'description')
    raw_id_fields = ('prisoner', 'received_by')
    readonly_fields = ('current_amount',)
    inlines = [PrisonerItemTransactionInline]

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


@admin.register(InmateReturn)
class InmateReturnAdmin(admin.ModelAdmin):
    list_display = ('title', 'return_type', 'station', 'created_by', 'created_at', 'status', 'get_file_size_display')
    list_filter = ('return_type', 'station', 'status', 'month', 'year', 'created_at')
    search_fields = ('title', 'file_name', 'created_by__username', 'station__name')
    readonly_fields = ('created_at', 'updated_at', 'file_size', 'file_type', 'file_name', 'region')
    date_hierarchy = 'created_at'
    inlines = [InmateReturnDataInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'return_type', 'description', 'status')
        }),
        ('Period Information', {
            'fields': ('month', 'year', 'start_date', 'end_date', 'reporting_period')
        }),
        ('Station Information', {
            'fields': ('station', 'region')
        }),
        ('File Information', {
            'fields': ('file', 'file_name', 'file_size', 'file_type', 'file_hash', 'file_uploaded_at')
        }),
        ('CSV Data', {
            'fields': ('has_csv_data', 'csv_row_count', 'csv_imported_at', 'csv_imported_by')
        }),
        ('Approval Workflow', {
            'fields': (
                'status_history', 'submitted_at', 'submitted_by',
                'approved_at', 'approved_by', 'approval_notes',
                'rejected_at', 'rejected_by', 'rejection_reason',
                'completed_at', 'completed_by'
            )
        }),
        ('Review Assignment', {
            'fields': ('assigned_to', 'review_deadline')
        }),
        ('Statistics', {
            'fields': ('total_records', 'unique_prisoners', 'male_count', 'female_count')
        }),
        ('Metadata', {
            'fields': ('offense_breakdown', 'age_distribution', 'summary_data')
        }),
        ('Notes & Permissions', {
            'fields': ('remarks', 'internal_notes', 'is_public', 'is_template')
        }),
        ('Audit Trail', {
            'fields': ('created_by', 'created_at', 'updated_at', 'last_accessed_at', 'version')
        }),
        ('Tags & Custom', {
            'fields': ('tags', 'custom_fields')
        }),
    )
    
    def get_file_size_display(self, obj):
        """Display file size in human-readable format"""
        if obj.file_size:
            size = obj.file_size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        return "N/A"
    get_file_size_display.short_description = 'File Size'
    
    def get_inlines(self, request, obj=None):
        """Only show the inline if the return has data"""
        if obj and obj.has_csv_data:
            return [InmateReturnDataInline]
        return []
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('station', 'region', 'created_by')


@admin.register(InmateReturnData)
class InmateReturnDataAdmin(admin.ModelAdmin):
    list_display = (
        'inmate_return', 'row_number', 'serial_no', 'prisoner_number', 
        'full_name', 'sex', 'age', 'offense'
    )
    list_filter = (
        'inmate_return__return_type', 'inmate_return__station', 
        'sex', 'inmate_return__status'
    )
    search_fields = (
        'prisoner_number', 'full_name', 'first_name', 'surname', 
        'offense', 'court', 'village', 'district'
    )
    # Remove 'created_at' and 'updated_at' from readonly_fields
    readonly_fields = ()
    fieldsets = (
        ('Return Information', {
            'fields': ('inmate_return', 'row_number', 'serial_no')
        }),
        ('Prisoner Identification', {
            'fields': ('prisoner_number', 'full_name', 'first_name', 'surname', 'middle_name')
        }),
        ('Demographics', {
            'fields': ('sex', 'age', 'date_of_birth')
        }),
        ('Prisoner Classification', {
            'fields': ('prisoner_class', 'is_convicted', 'is_remand')
        }),
        ('Offense & Court', {
            'fields': ('offense', 'offense_code', 'court', 'court_case_number', 'judge_name', 'case_status')
        }),
        ('Sentence Details', {
            'fields': ('sentence_months', 'sentence_years', 'sentence_days', 'sentence_type')
        }),
        ('Dates', {
            'fields': (
                'date_of_committal', 'date_of_admission', 'date_of_conviction',
                'date_of_sentence', 'release_date_without_remission', 
                'release_date_with_remission', 'expected_date_release',
                'actual_release_date', 'last_court_appearance', 'next_court_date'
            )
        }),
        ('Remission & Reductions', {
            'fields': ('remission_months', 'reduction_months', 'reduction_reason', 'amnesty_earned')
        }),
        ('Location', {
            'fields': ('village', 'chief', 'district', 'region_location', 'country', 'nationality', 'home_location')
        }),
        ('Identification', {
            'fields': ('national_id', 'passport_number', 'driving_license', 'phone_number')
        }),
        ('Previous Convictions', {
            'fields': ('previous_conviction_particulars', 'previous_conviction_count', 'is_recidivist')
        }),
        ('Conduct', {
            'fields': ('conduct', 'behavior_rating')
        }),
        ('Medical & Special Categories', {
            'fields': (
                'is_chronically_ill', 'illness_description', 'is_pregnant', 
                'gestation_period', 'is_elderly'
            )
        }),
        ('Children Information', {
            'fields': (
                'has_children', 'children_count', 'child_name', 
                'child_age', 'child_sex', 'children_details'
            )
        }),
        ('Arrest Information', {
            'fields': ('arresting_authority', 'date_of_arrest', 'place_of_arrest')
        }),
        ('Additional Fields', {
            'fields': ('cell_block', 'cell_number', 'prisoner_type', 'security_level')
        }),
        ('Remarks', {
            'fields': ('remarks', 'special_remarks')
        }),
        ('Additional Data', {
            'fields': ('additional_data',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('inmate_return', 'inmate_return__station')


@admin.register(ReturnTemplate)
class ReturnTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'return_type', 'is_active', 'is_default', 'version', 'created_at')
    list_filter = ('return_type', 'is_active', 'is_default')
    search_fields = ('name', 'description', 'return_type')
    readonly_fields = ('created_at', 'updated_at', 'version')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'return_type', 'description', 'is_active', 'is_default')
        }),
        ('Columns Configuration', {
            'fields': ('columns', 'column_groups'),
            'classes': ('wide', 'collapse'),
            'description': 'Define columns as JSON. Each column should have: key, header, type, required'
        }),
        ('Sample Data', {
            'fields': ('sample_data',),
            'classes': ('wide', 'collapse')
        }),
        ('Audit', {
            'fields': ('version', 'created_by', 'created_at', 'updated_at')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Set created_by on creation"""
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(FingerprintDevice)
class FingerprintDeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'device_type', 'serial_number', 'status', 'prison_station', 'last_used_at')
    list_filter = ('device_type', 'status', 'prison_station')
    search_fields = ('name', 'serial_number', 'notes')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(FingerprintMatch)
class FingerprintMatchAdmin(admin.ModelAdmin):
    list_display = ('searched_prisoner', 'matched_prisoner', 'match_score', 'match_status', 'search_timestamp', 'searched_by')
    list_filter = ('match_status', 'search_timestamp')
    search_fields = ('searched_prisoner__prisoner_number', 'matched_prisoner__prisoner_number')
    readonly_fields = ('search_timestamp',)


@admin.register(FingerprintAuditLog)
class FingerprintAuditLogAdmin(admin.ModelAdmin):
    list_display = ('prisoner', 'operation', 'performed_by', 'performed_at', 'success')
    list_filter = ('operation', 'success', 'performed_at')
    search_fields = ('prisoner__prisoner_number', 'error_message')
    readonly_fields = ('performed_at',)


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'prisoner', 'relationship', 'visit_date', 'visit_time', 'is_approved')
    list_filter = ('is_approved', 'relationship', 'visit_date')
    search_fields = ('first_name', 'surname', 'prisoner__prisoner_number', 'prisoner__first_name')
    raw_id_fields = ('prisoner', 'approved_by', 'created_by')
    readonly_fields = ('created_at', 'last_updated')


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ('prisoner', 'record_date', 'category', 'diagnosis', 'next_checkup')
    list_filter = ('category', 'record_date', 'next_checkup')
    search_fields = ('prisoner__prisoner_number', 'prisoner__first_name', 'prisoner__surname', 'diagnosis')
    raw_id_fields = ('prisoner', 'recorded_by')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(IncidentReport)
class IncidentReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'severity', 'date_occurred', 'location', 'follow_up_required')
    list_filter = ('severity', 'date_occurred', 'follow_up_required')
    search_fields = ('title', 'description', 'location')
    raw_id_fields = ('reported_by',)
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('involved_prisoners',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'notification_type', 'priority', 'is_read', 'created_at')
    list_filter = ('notification_type', 'priority', 'is_read', 'created_at')
    search_fields = ('title', 'message')
    raw_id_fields = ('prisoner', 'medical_record', 'read_by')
    filter_horizontal = ('target_users',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PrisonerReleaseReview)
class PrisonerReleaseReviewAdmin(admin.ModelAdmin):
    list_display = ('prisoner', 'review_role', 'status', 'release_date', 'requested_at')
    list_filter = ('review_role', 'status', 'requested_at')
    search_fields = ('prisoner__prisoner_number', 'prisoner__first_name', 'prisoner__surname')
    raw_id_fields = ('prisoner', 'requested_by', 'reviewed_by')
    readonly_fields = ('requested_at', 'reviewed_at')


# Keep track of all registered models
admin.site.site_header = "Prison Management System Administration"
admin.site.site_title = "PMS Admin"
admin.site.index_title = "Welcome to Prison Management System"