from django.contrib import admin
from .models import (
    ReturnTemplate, ReturnSubmission, ReturnData, 
    RegionalReturnSummary, StationReturnStatus,
    MonthlySubmissionTracker, ReturnTypeStatus
)


@admin.register(ReturnTemplate)
class ReturnTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_default', 'is_active', 'created_at')
    list_filter = ('category', 'is_default', 'is_active')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ReturnSubmission)
class ReturnSubmissionAdmin(admin.ModelAdmin):
    list_display = ('template', 'prison_station', 'period_display', 'status', 
                    'submitted_by', 'submission_date_display', 'row_count', 'error_count')
    list_filter = ('status', 'template__category', 'prison_station', 'year', 'month')
    search_fields = ('template__name', 'prison_station__name', 'submitted_by__username')
    readonly_fields = ('submitted_at', 'processed_at')
    list_select_related = ('template', 'prison_station', 'submitted_by')
    date_hierarchy = 'submitted_at'
    
    def period_display(self, obj):
        return obj.period_display
    period_display.short_description = "Period"
    
    def submission_date_display(self, obj):
        return obj.submission_date_display
    submission_date_display.short_description = "Submitted Date"


@admin.register(ReturnData)
class ReturnDataAdmin(admin.ModelAdmin):
    list_display = ('submission', 'prisoner_number', 'name', 'sex', 'age', 'offense', 'is_valid')
    list_filter = ('sex', 'is_valid', 'submission__template__category')
    search_fields = ('prisoner_number', 'name', 'offense')
    list_select_related = ('submission',)


@admin.register(RegionalReturnSummary)
class RegionalReturnSummaryAdmin(admin.ModelAdmin):
    list_display = ('category', 'region', 'period', 'period_type', 'total_records', 'generated_at')
    list_filter = ('region', 'category', 'period_type', 'year', 'month')
    search_fields = ('region', 'period', 'category')


@admin.register(StationReturnStatus)
class StationReturnStatusAdmin(admin.ModelAdmin):
    list_display = ('prison_station', 'template', 'period_display', 'status', 
                    'submitted_at', 'approved_at', 'updated_at')
    list_filter = ('status', 'period', 'template__category', 'prison_station__region', 'year', 'month')
    search_fields = ('prison_station__name', 'template__name', 'period')
    list_select_related = ('prison_station', 'template')
    
    def period_display(self, obj):
        return obj.period_display
    period_display.short_description = "Period"


@admin.register(MonthlySubmissionTracker)
class MonthlySubmissionTrackerAdmin(admin.ModelAdmin):
    list_display = ('prison_station', 'period_display', 'total_required', 
                    'total_submitted', 'total_approved', 'total_rejected', 
                    'is_complete', 'last_updated')
    list_filter = ('year', 'month', 'is_complete', 'prison_station__region')
    search_fields = ('prison_station__name', 'period')
    list_select_related = ('prison_station',)
    
    def period_display(self, obj):
        return obj.period_display
    period_display.short_description = "Period"


@admin.register(ReturnTypeStatus)
class ReturnTypeStatusAdmin(admin.ModelAdmin):
    list_display = ('prison_station', 'template', 'period_display', 'status', 
                    'submitted_at', 'approved_at', 'updated_at')
    list_filter = ('status', 'year', 'month', 'template__category', 'prison_station__region')
    search_fields = ('prison_station__name', 'template__name', 'period')
    list_select_related = ('prison_station', 'template')
    
    def period_display(self, obj):
        return obj.period_display
    period_display.short_description = "Period"