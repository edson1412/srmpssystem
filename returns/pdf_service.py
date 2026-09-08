"""
PDF generation service for returns.
"""
import io
from datetime import datetime
from django.http import HttpResponse
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from django.utils.html import escape
import html


class ReturnPDFService:
    """Service for generating PDF exports of return data."""
    
    @staticmethod
    def generate_return_pdf(submission, user=None):
        """
        Generate PDF for a single return submission.
        """
        context = {
            'submission': submission,
            'data_rows': submission.data_rows.all().order_by('row_number'),
            'generated_at': datetime.now(),
            'generated_by': user.get_full_name() if user else 'System',
            'station_name': submission.prison_station.name,
            'period_display': submission.period_display,
            'template_name': submission.template.name,
            'total_records': submission.row_count,
            'total_male': submission.total_male,
            'total_female': submission.total_female,
        }
        
        template_path = 'returns/pdf/return_submission_pdf.html'
        return ReturnPDFService._render_pdf(template_path, context, 
            f"return_{submission.template.category}_{submission.prison_station.code}_{submission.period}.pdf")
    
    @staticmethod
    def generate_station_returns_pdf(station, template, period, user=None):
        """
        Generate PDF for all returns of a specific template type for a station.
        """
        # Get all submissions for this station/template/period
        submissions = template.submissions.filter(
            prison_station=station,
            period=period
        ).order_by('submitted_at')
        
        context = {
            'submissions': submissions,
            'station': station,
            'template': template,
            'period': period,
            'generated_at': datetime.now(),
            'generated_by': user.get_full_name() if user else 'System',
            'total_submissions': submissions.count(),
        }
        
        template_path = 'returns/pdf/station_returns_pdf.html'
        return ReturnPDFService._render_pdf(template_path, context, 
            f"station_returns_{station.code}_{template.category}_{period}.pdf")
    
    @staticmethod
    def generate_regional_returns_pdf(region, template, period, user=None):
        """
        Generate PDF for all returns of a specific template type for a region.
        """
        # Get stations in this region
        stations = region.prisonstation_set.all() if hasattr(region, 'prisonstation_set') else []
        
        # Get submissions for these stations
        submissions = template.submissions.filter(
            prison_station__in=stations,
            period=period
        ).select_related('prison_station', 'submitted_by').order_by('prison_station__name', 'submitted_at')
        
        # Group by station
        station_data = {}
        for submission in submissions:
            station_name = submission.prison_station.name
            if station_name not in station_data:
                station_data[station_name] = {
                    'station': submission.prison_station,
                    'submissions': [],
                    'total_records': 0,
                    'male': 0,
                    'female': 0,
                }
            station_data[station_name]['submissions'].append(submission)
            station_data[station_name]['total_records'] += submission.row_count
            station_data[station_name]['male'] += submission.total_male
            station_data[station_name]['female'] += submission.total_female
        
        context = {
            'station_data': station_data,
            'region_name': region.get_region_display() if hasattr(region, 'get_region_display') else str(region),
            'template': template,
            'period': period,
            'generated_at': datetime.now(),
            'generated_by': user.get_full_name() if user else 'System',
            'total_stations': len(station_data),
        }
        
        template_path = 'returns/pdf/regional_returns_pdf.html'
        return ReturnPDFService._render_pdf(template_path, context, 
            f"regional_returns_{region}_{template.category}_{period}.pdf")
    
    @staticmethod
    def generate_all_returns_pdf(template, period, user=None):
        """
        Generate PDF for all returns of a specific template type for all stations.
        """
        # Get all submissions for this template and period
        submissions = template.submissions.filter(
            period=period
        ).select_related('prison_station', 'submitted_by').order_by('prison_station__name', 'submitted_at')
        
        # Group by station
        station_data = {}
        for submission in submissions:
            station_name = submission.prison_station.name
            if station_name not in station_data:
                station_data[station_name] = {
                    'station': submission.prison_station,
                    'submissions': [],
                    'total_records': 0,
                    'male': 0,
                    'female': 0,
                }
            station_data[station_name]['submissions'].append(submission)
            station_data[station_name]['total_records'] += submission.row_count
            station_data[station_name]['male'] += submission.total_male
            station_data[station_name]['female'] += submission.total_female
        
        context = {
            'station_data': station_data,
            'template': template,
            'period': period,
            'generated_at': datetime.now(),
            'generated_by': user.get_full_name() if user else 'System',
            'total_stations': len(station_data),
            'total_submissions': submissions.count(),
            'total_records': sum(s.row_count for s in submissions),
        }
        
        template_path = 'returns/pdf/all_stations_returns_pdf.html'
        return ReturnPDFService._render_pdf(template_path, context, 
            f"all_returns_{template.category}_{period}.pdf")
    
    @staticmethod
    def _render_pdf(template_path, context, filename):
        """
        Render a template to PDF.
        """
        html_string = render_to_string(template_path, context)
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Create PDF
        pisa_status = pisa.CreatePDF(
            html_string, dest=response, encoding='utf-8'
        )
        
        if pisa_status.err:
            return HttpResponse(f'We had some errors <pre>{html_string}</pre>')
        
        return response