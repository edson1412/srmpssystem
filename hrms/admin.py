# hrms/admin.py

from django.contrib import admin
from django.contrib import messages
from .models import (
    Rank, Officer, Education, PromotionHistory, TransferHistory,
    LeaveType, LeaveRequest, AnnualLeaveBalance, OfficerDocument,
    PerformanceMetric, OfficerPerformance, Attendance, DisciplinaryCase,
    OfficeAssignment, TrainingIntake, TrainingCourse,
    Recruit, RecruitMark
)
from accounts.models import CustomUser # Import CustomUser for raw_id_fields
from .email_utils import send_leave_reminder_email

# Inlines for Officer Model
class EducationInline(admin.TabularInline):
    """Inline for Education Qualifications within Officer admin."""
    model = Education
    extra = 1 # Number of empty forms to display
    fields = ('institution', 'qualification', 'year_obtained', 'supporting_document')
    # 'officer' field is implicitly handled by the inline, no need for raw_id_fields here

class PromotionHistoryInline(admin.TabularInline):
    """Inline for Promotion History within Officer admin."""
    model = PromotionHistory
    extra = 0 # Don't show empty forms by default
    fields = ('previous_rank', 'new_rank', 'promotion_date', 'notes')
    raw_id_fields = ('previous_rank', 'new_rank', 'recorded_by')
    readonly_fields = ('recorded_by',) # Recorded by is set by view/auto_now_add

class TransferHistoryInline(admin.TabularInline):
    """Inline for Transfer History within Officer admin."""
    model = TransferHistory
    extra = 0
    fields = ('previous_station', 'new_station', 'transfer_date', 'notes')
    raw_id_fields = ('previous_station', 'new_station', 'recorded_by')
    readonly_fields = ('recorded_by',)

class LeaveRequestInline(admin.TabularInline):
    """Inline for Leave Requests within Officer admin."""
    model = LeaveRequest
    extra = 0
    fields = ('leave_type', 'start_date', 'number_of_days', 'end_date', 'status', 'supporting_document', 'rejection_notes', 'approved_by', 'approved_at')
    raw_id_fields = ('leave_type', 'approved_by')
    readonly_fields = ('end_date', 'requested_at', 'approved_by', 'approved_at') # End date is auto-calculated, timestamps are auto
    show_change_link = True # Allow clicking to full leave request detail

class OfficerDocumentInline(admin.TabularInline):
    """Inline for Officer Documents within Officer admin."""
    model = OfficerDocument
    extra = 0
    fields = ('file_name', 'file_type', 'document', 'action_to', 'status', 'notes', 'uploaded_by', 'uploaded_at', 'reviewed_by', 'reviewed_at')
    raw_id_fields = ('uploaded_by', 'reviewed_by')
    readonly_fields = ('uploaded_at', 'reviewed_at')
    show_change_link = True

class OfficerPerformanceInline(admin.TabularInline):
    """Inline for Officer Performance records within Officer admin."""
    model = OfficerPerformance
    extra = 0
    fields = ('metric', 'date', 'score', 'notes', 'recorded_by', 'created_at')
    raw_id_fields = ('metric', 'recorded_by')
    readonly_fields = ('created_at',)

class AttendanceInline(admin.TabularInline):
    """Inline for Attendance records within Officer admin."""
    model = Attendance
    extra = 0
    fields = ('date', 'status', 'remarks', 'marked_by', 'created_at')
    raw_id_fields = ('marked_by',)
    readonly_fields = ('created_at',)

class DisciplinaryCaseInline(admin.TabularInline):
    """Inline for Disciplinary Cases within Officer admin."""
    model = DisciplinaryCase
    extra = 0
    fields = ('case_date', 'offense', 'description', 'action_taken', 'action_date', 'recorded_by', 'created_at')
    raw_id_fields = ('recorded_by',)
    readonly_fields = ('created_at', 'updated_at')


# Admin classes for each model
@admin.register(Rank)
class RankAdmin(admin.ModelAdmin):
    list_display = ('name', 'leave_days_annual')
    search_fields = ('name',)
    list_filter = ('leave_days_annual',)

@admin.register(OfficeAssignment)
class OfficeAssignmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(Officer)
class OfficerAdmin(admin.ModelAdmin):
    list_display = (
        'service_number', 'employment_number', 'full_name', 'rank',
        'prison_station', 'status', 'date_joined_service',
        'period_of_service', 'months_until_retirement'
    )
    list_filter = ('status', 'rank', 'prison_station__region', 'prison_station', 'gender', 'marital_status')
    search_fields = (
        'service_number', 'employment_number', 'first_name', 'middle_name', 'surname',
        'email', 'contact_number', 'village', 'traditional_authority', 'district'
    )
    raw_id_fields = ('rank', 'region', 'prison_station', 'current_office_assignment')
    readonly_fields = ('period_of_service', 'months_until_retirement', 'created_at', 'updated_at')
    inlines = [
        EducationInline,
        PromotionHistoryInline,
        TransferHistoryInline,
        LeaveRequestInline,
        OfficerDocumentInline,
        OfficerPerformanceInline,
        AttendanceInline,
        DisciplinaryCaseInline,
    ]
    fieldsets = (
        (None, {'fields': ('officer_picture', 'service_number', 'employment_number', 'status', 'gender', 'first_name', 'middle_name', 'surname', 'date_of_birth', 'date_joined_service', 'rank', 'current_office_assignment')}),
        ('Contact Information', {'fields': ('contact_number', 'email')}),
        ('Location Information', {'fields': ('village', 'traditional_authority', 'district', 'region', 'prison_station')}),
        ('Family Information', {'fields': ('marital_status', 'spouse_name', 'number_of_children')}),
        ('Next of Kin', {'fields': ('next_of_kin_name', 'next_of_kin_relationship', 'next_of_kin_location', 'next_of_kin_contact')}),
        ('Skills & Languages', {'fields': ('notable_skills', 'languages_spoken')}),
        ('Auto-Calculated Fields', {'fields': ('period_of_service', 'months_until_retirement')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def get_queryset(self, request):
        # Prefetch related data for efficiency in list display
        return super().get_queryset(request).select_related('rank', 'prison_station', 'region')

    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'Full Name'


@admin.register(PromotionHistory)
class PromotionHistoryAdmin(admin.ModelAdmin):
    list_display = ('officer', 'previous_rank', 'new_rank', 'promotion_date', 'recorded_by')
    list_filter = ('promotion_date', 'previous_rank', 'new_rank', 'officer__prison_station__region')
    search_fields = ('officer__service_number', 'officer__first_name', 'officer__surname', 'notes')
    raw_id_fields = ('officer', 'previous_rank', 'new_rank', 'recorded_by')
    date_hierarchy = 'promotion_date'

@admin.register(TransferHistory)
class TransferHistoryAdmin(admin.ModelAdmin):
    list_display = ('officer', 'previous_station', 'new_station', 'transfer_date', 'recorded_by')
    list_filter = ('transfer_date', 'previous_station__region', 'new_station__region')
    search_fields = ('officer__service_number', 'officer__first_name', 'officer__surname', 'notes')
    raw_id_fields = ('officer', 'previous_station', 'new_station', 'recorded_by')
    date_hierarchy = 'transfer_date'

@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'default_days', 'is_maternity', 'is_study')
    search_fields = ('name',)
    list_filter = ('is_maternity', 'is_study')

@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = (
        'officer', 'leave_type', 'start_date', 'end_date', 'number_of_days',
        'status', 'requested_at', 'approved_by', 'approved_at'
    )
    list_filter = ('status', 'leave_type', 'officer__prison_station__region', 'officer__prison_station')
    search_fields = (
        'officer__service_number', 'officer__first_name', 'officer__surname',
        'leave_type__name', 'rejection_notes'
    )
    raw_id_fields = ('officer', 'leave_type', 'approved_by')
    readonly_fields = ('end_date', 'requested_at', 'approved_at')
    date_hierarchy = 'requested_at'
    actions = ['send_reminder_emails']

    def send_reminder_emails(self, request, queryset):
        """
        Admin action to send reminder emails for selected leave requests.
        This will send reminders to officers whose leave ends in 3 days.
        """
        result = send_leave_reminder_email()
        
        if result['total_processed'] > 0:
            self.message_user(
                request,
                f"Successfully sent {result['success_count']} reminder emails. "
                f"Failed: {result['failure_count']}",
                messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                "No officers with leave ending in 3 days found.",
                messages.WARNING
            )
    
    send_reminder_emails.short_description = "Send reminder emails for leave ending in 3 days"

@admin.register(AnnualLeaveBalance)
class AnnualLeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ('officer', 'year', 'total_days_entitled', 'days_taken', 'remaining_days', 'last_reset_date')
    list_filter = ('year', 'officer__prison_station__region', 'officer__prison_station')
    search_fields = ('officer__service_number', 'officer__first_name', 'officer__surname')
    raw_id_fields = ('officer',)
    readonly_fields = ('remaining_days',) # Calculated property

@admin.register(OfficerDocument)
class OfficerDocumentAdmin(admin.ModelAdmin):
    list_display = (
        'officer', 'file_name', 'file_type', 'uploaded_at', 'action_to',
        'status', 'reviewed_by', 'reviewed_at'
    )
    list_filter = ('file_type', 'status', 'action_to', 'officer__prison_station__region')
    search_fields = (
        'officer__service_number', 'officer__first_name', 'officer__surname',
        'file_name', 'notes'
    )
    raw_id_fields = ('officer', 'uploaded_by', 'reviewed_by')
    date_hierarchy = 'uploaded_at'

@admin.register(PerformanceMetric)
class PerformanceMetricAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(OfficerPerformance)
class OfficerPerformanceAdmin(admin.ModelAdmin):
    list_display = ('officer', 'metric', 'date', 'score', 'recorded_by')
    list_filter = ('metric', 'date', 'officer__prison_station__region')
    search_fields = ('officer__service_number', 'officer__first_name', 'officer__surname', 'notes')
    raw_id_fields = ('officer', 'metric', 'recorded_by')
    date_hierarchy = 'date'

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('officer', 'date', 'status', 'marked_by')
    list_filter = ('status', 'date', 'officer__prison_station__region')
    search_fields = ('officer__service_number', 'officer__first_name', 'officer__surname', 'remarks')
    raw_id_fields = ('officer', 'marked_by')
    date_hierarchy = 'date'

@admin.register(DisciplinaryCase)
class DisciplinaryCaseAdmin(admin.ModelAdmin):
    list_display = ('officer', 'case_date', 'offense', 'action_taken', 'action_date', 'recorded_by')
    list_filter = ('action_taken', 'case_date', 'officer__prison_station__region')
    search_fields = ('officer__service_number', 'officer__first_name', 'officer__surname', 'offense', 'description')
    raw_id_fields = ('officer', 'recorded_by')
    date_hierarchy = 'case_date'


# Training Wing Admin Classes

class RecruitMarkInline(admin.TabularInline):
    """Inline for Recruit Marks within Recruit admin."""
    model = RecruitMark
    extra = 0
    fields = ('course', 'obtained_marks', 'exam_date', 'remarks', 'recorded_by')
    raw_id_fields = ('course', 'recorded_by')
    readonly_fields = ('percentage', 'grade')

@admin.register(TrainingIntake)
class TrainingIntakeAdmin(admin.ModelAdmin):
    list_display = ('intake_number', 'year', 'start_date', 'pass_out_date', 'estimated_end_date', 'is_active', 'created_by')
    list_filter = ('year', 'is_active', 'start_date')
    search_fields = ('intake_number', 'description')
    raw_id_fields = ('created_by',)
    date_hierarchy = 'start_date'

@admin.register(TrainingCourse)
class TrainingCourseAdmin(admin.ModelAdmin):
    list_display = ('course_code', 'name', 'category', 'total_marks', 'passing_mark', 'is_active')
    list_filter = ('is_active', 'category', 'course_code')
    search_fields = ('course_code', 'name', 'description')
    readonly_fields = ('name',)  # This is auto-generated from course_code
    ordering = ('category', 'display_order', 'course_code')

@admin.register(Recruit)
class RecruitAdmin(admin.ModelAdmin):
    list_display = ('service_number', 'full_name', 'intake', 'recruit_type', 'status', 'final_grade')
    list_filter = ('status', 'recruit_type', 'gender', 'intake__year')
    search_fields = ('service_number', 'first_name', 'middle_name', 'surname', 'email', 'contact_number', 'next_of_kin')
    raw_id_fields = ('intake', 'created_by')
    inlines = [RecruitMarkInline]
    readonly_fields = ('full_name', 'final_grade')
    actions = ['export_marks_csv', 'export_marks_excel']
    fieldsets = (
        (None, {'fields': ('intake', 'service_number', 'recruit_type', 'status')}),
        ('Personal Information', {'fields': ('first_name', 'middle_name', 'surname', 'date_of_birth', 'gender')}),
        ('Contact Information', {'fields': ('contact_number', 'email', 'home_district')}),
        ('Next of Kin Information', {'fields': ('next_of_kin', 'next_of_kin_relationship', 'next_of_kin_contact', 'next_of_kin_address')}),
        ('Auto-Calculated Fields', {'fields': ('full_name', 'final_grade')}),
        ('System Fields', {'fields': ('created_by',), 'classes': ('collapse',)}),
    )

    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'Full Name'
    
    def export_marks_csv(self, request, queryset):
        """Export marks for selected recruits as CSV"""
        import csv
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="recruit_marks_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['recruit_training_id', 'recruit_name', 'course_code', 'course_name', 
                        'obtained_marks', 'percentage', 'grade', 'exam_date', 'remarks'])
        
        for recruit in queryset:
            marks = recruit.marks.select_related('course').all()
            for mark in marks:
                writer.writerow([
                    recruit.training_id,
                    recruit.full_name,
                    mark.course.course_code,
                    mark.course.name,
                    mark.obtained_marks,
                    mark.percentage,
                    mark.grade,
                    mark.exam_date,
                    mark.remarks
                ])
        
        return response
    export_marks_csv.short_description = "Export selected recruits' marks to CSV"
    
    def export_marks_excel(self, request, queryset):
        """Export marks for selected recruits as Excel"""
        import pandas as pd
        from io import BytesIO
        
        data = []
        for recruit in queryset:
            marks = recruit.marks.select_related('course').all()
            for mark in marks:
                data.append({
                    'recruit_training_id': recruit.training_id,
                    'recruit_name': recruit.full_name,
                    'course_code': mark.course.course_code,
                    'course_name': mark.course.name,
                    'obtained_marks': mark.obtained_marks,
                    'percentage': mark.percentage,
                    'grade': mark.grade,
                    'exam_date': mark.exam_date,
                    'remarks': mark.remarks
                })
        
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Recruit Marks', index=False)
        
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="recruit_marks_export.xlsx"'
        return response
    export_marks_excel.short_description = "Export selected recruits' marks to Excel"

@admin.register(RecruitMark)
class RecruitMarkAdmin(admin.ModelAdmin):
    list_display = ('recruit', 'course', 'obtained_marks', 'percentage', 'grade', 'exam_date', 'recorded_by')
    list_filter = ('course', 'exam_date')
    search_fields = ('recruit__service_number', 'recruit__first_name', 'recruit__surname', 'course__name')
    raw_id_fields = ('recruit', 'course', 'recorded_by')
    readonly_fields = ('percentage', 'grade')
    date_hierarchy = 'exam_date'

