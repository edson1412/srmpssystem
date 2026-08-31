# import_export_utils.py
import csv
import io
import logging
from datetime import datetime
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import InmateReturn, InmateReturnData, ReturnTemplate

logger = logging.getLogger(__name__)


class ReturnDataImporter:
    """Handles CSV import for inmate return data"""
    
    # Field mapping for common variations in CSV headers
    HEADER_MAPPING = {
        'ser. no.': 'serial_no',
        'ser no': 'serial_no',
        's/no': 'serial_no',
        's/n': 'serial_no',
        'no': 'serial_no',
        'pris. no': 'prisoner_number',
        'pri. no': 'prisoner_number',
        'pris no': 'prisoner_number',
        'pri no': 'prisoner_number',
        'prisoner no': 'prisoner_number',
        'name': 'full_name',
        'names': 'full_name',
        'full name': 'full_name',
        'sex': 'sex',
        'age': 'age',
        'offence': 'offense',
        'offense': 'offense',
        'court': 'court',
        'court/case no': 'court',
        'court case no': 'court',
        'case no': 'court',
        'sentence': 'sentence_months',
        'sent.': 'sentence_months',
        'sent': 'sentence_months',
        'village': 'village',
        'v': 'village',
        't/a': 'chief',
        'chief': 'chief',
        'd.': 'district',
        'district': 'district',
        'country': 'country',
        'nationality': 'nationality',
        'date of committal': 'date_of_committal',
        'doc': 'date_of_committal',
        'date of admission': 'date_of_admission',
        'doa': 'date_of_admission',
        'date of conv.': 'date_of_conviction',
        'date of conviction': 'date_of_conviction',
        'expiry date of release without remission': 'release_date_without_remission',
        'expiry date of release with rem.': 'release_date_with_remission',
        'edr': 'expected_date_release',
        'expected date of release': 'expected_date_release',
        'due date': 'expected_date_release',
        'arresting authority': 'arresting_authority',
        'last court appearance': 'last_court_appearance',
        'judge name': 'judge_name',
        'status': 'case_status',
        'case status': 'case_status',
        'pre-trial period': 'pre_trial_period',
        'sentence served': 'sentence_served',
        'sent. served': 'sentence_served',
        'amnesty earned': 'amnesty_earned',
        'particulars of previous conviction': 'previous_conviction_particulars',
        'conduct': 'conduct',
        'name of a child': 'child_name',
        'child name': 'child_name',
        'child age': 'child_age',
        'child sex': 'child_sex',
        'gestation period': 'gestation_period',
        'remarks': 'remarks',
        'remarks i.e loss of remission': 'remarks',
        'edr after amnesty': 'release_date_with_remission',
        'rem no.': 'prisoner_number',
        'rem no': 'prisoner_number',
        'expected date of release': 'expected_date_release',
        'date of conv': 'date_of_conviction',
    }
    
    def __init__(self, inmate_return, csv_file):
        self.inmate_return = inmate_return
        self.csv_file = csv_file
        self.errors = []
        self.warnings = []
        self.imported_count = 0
        
    def import_data(self):
        """Main import method"""
        self.errors = []
        self.warnings = []
        self.imported_count = 0
        
        try:
            # Read CSV content
            content = self.csv_file.read().decode('utf-8')
            csv_reader = csv.reader(io.StringIO(content))
            rows = list(csv_reader)
            
            if not rows:
                self.errors.append("CSV file is empty")
                return False
            
            # Get headers from first row
            headers = self._clean_headers(rows[0])
            
            # Map headers to model fields
            field_map = self._map_headers_to_fields(headers)
            
            # Process data rows
            for row_idx, row in enumerate(rows[1:], start=1):
                if not row or all(cell.strip() == '' for cell in row):
                    continue  # Skip empty rows
                
                # Ensure row has enough columns
                row_data = self._create_row_data(row, field_map, len(headers))
                
                if row_data:
                    self._save_row_data(row_data, row_idx)
                    self.imported_count += 1
                    
        except Exception as e:
            logger.error(f"Error importing CSV: {str(e)}")
            self.errors.append(f"Error importing data: {str(e)}")
            return False
        
        # Update the inmate return status
        if self.imported_count > 0:
            self.inmate_return.status = 'submitted'
            self.inmate_return.save()
            return True
        else:
            self.errors.append("No data rows were imported")
            return False
    
    def _clean_headers(self, headers):
        """Clean and normalize headers"""
        return [self._clean_header(h) for h in headers]
    
    def _clean_header(self, header):
        """Clean a single header string"""
        # Remove leading/trailing whitespace and normalize
        cleaned = header.strip().lower()
        # Remove special characters
        cleaned = ''.join(c for c in cleaned if c.isalnum() or c in ' ./-')
        return cleaned
    
    def _map_headers_to_fields(self, headers):
        """Map CSV headers to model field names"""
        field_map = {}
        
        for idx, header in enumerate(headers):
            # Try direct mapping
            if header in self.HEADER_MAPPING:
                field_map[idx] = self.HEADER_MAPPING[header]
            else:
                # Try partial match
                for csv_header, model_field in self.HEADER_MAPPING.items():
                    if csv_header in header or header in csv_header:
                        field_map[idx] = model_field
                        break
                    
        return field_map
    
    def _create_row_data(self, row, field_map, expected_cols):
        """Create a dictionary of row data mapped to model fields"""
        row_data = {}
        
        for idx, value in enumerate(row):
            value = value.strip()
            if idx in field_map and value:
                field_name = field_map[idx]
                row_data[field_name] = value
        
        # Add row number
        row_data['row_number'] = self.imported_count + 1
        
        return row_data
    
    def _save_row_data(self, row_data, row_idx):
        """Save a single row of data to the database"""
        try:
            data_obj = InmateReturnData(inmate_return=self.inmate_return)
            
            # Map and convert field values
            for field_name, value in row_data.items():
                if field_name == 'row_number':
                    data_obj.row_number = value
                    continue
                    
                if hasattr(data_obj, field_name):
                    # Convert date fields
                    if field_name in ['date_of_committal', 'date_of_admission', 'date_of_conviction',
                                      'release_date_without_remission', 'release_date_with_remission',
                                      'expected_date_release', 'last_court_appearance']:
                        converted = self._parse_date(value)
                        if converted:
                            setattr(data_obj, field_name, converted)
                    # Convert numeric fields
                    elif field_name in ['serial_no', 'age', 'child_age']:
                        try:
                            setattr(data_obj, field_name, int(value))
                        except ValueError:
                            pass
                    elif field_name in ['sentence_months']:
                        try:
                            setattr(data_obj, field_name, float(value))
                        except ValueError:
                            pass
                    # Regular string fields
                    else:
                        setattr(data_obj, field_name, value[:255])  # Truncate if too long
            
            data_obj.save()
            
        except Exception as e:
            logger.error(f"Error saving row {row_idx}: {str(e)}")
            self.warnings.append(f"Error saving row {row_idx}: {str(e)}")
    
    def _parse_date(self, value):
        """Parse date from various formats"""
        if not value:
            return None
        
        # Remove extra whitespace
        value = value.strip()
        
        # Try different date formats
        formats = ['%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d', '%d-%b-%Y', '%d %b %Y']
        
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        
        # Try with month abbreviations
        if '/' in value or '-' in value:
            try:
                # Handle formats like 20-09-2025
                parts = value.replace('/', '-').split('-')
                if len(parts) == 3:
                    day, month, year = parts
                    # If month is text, try to convert
                    if not month.isdigit():
                        month_names = {
                            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
                            'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
                            'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                        }
                        month_lower = month[:3].lower()
                        if month_lower in month_names:
                            month = str(month_names[month_lower])
                    return datetime.strptime(f"{day}-{month}-{year}", '%d-%m-%Y').date()
            except ValueError:
                pass
        
        return None


class ReturnDataExporter:
    """Handles export of return data to CSV"""
    
    def __init__(self, inmate_return):
        self.inmate_return = inmate_return
        
    def export_to_csv(self):
        """Export data to CSV"""
        output = io.StringIO()
        
        try:
            template = ReturnTemplate.objects.get(return_type=self.inmate_return.return_type)
            columns = template.columns
        except ReturnTemplate.DoesNotExist:
            # Fallback to all available fields
            columns = [
                {'key': 'serial_no', 'header': 'Ser. No.'},
                {'key': 'prisoner_number', 'header': 'Prisoner No.'},
                {'key': 'full_name', 'header': 'Full Name'},
                {'key': 'sex', 'header': 'Sex'},
                {'key': 'age', 'header': 'Age'},
                {'key': 'offense', 'header': 'Offense'},
                {'key': 'remarks', 'header': 'Remarks'},
            ]
        
        # Get headers
        headers = [col['header'] for col in columns]
        
        # Write CSV
        writer = csv.writer(output)
        writer.writerow(headers)
        
        # Get data rows
        rows = self.inmate_return.data_rows.all().order_by('serial_no', 'row_number')
        
        for row in rows:
            row_data = []
            for col in columns:
                key = col['key']
                value = getattr(row, key, None)
                
                # Format values
                if isinstance(value, datetime):
                    value = value.strftime('%d-%m-%Y')
                elif isinstance(value, (int, float, Decimal)):
                    value = str(value)
                elif value is None:
                    value = ''
                    
                row_data.append(value)
            
            writer.writerow(row_data)
        
        return output.getvalue()
    
    def get_summary_data(self):
        """Get summary data for the return"""
        template = None
        try:
            template = ReturnTemplate.objects.get(return_type=self.inmate_return.return_type)
        except ReturnTemplate.DoesNotExist:
            pass
        
        # Get statistics
        total_rows = self.inmate_return.data_rows.count()
        
        # Get unique prisoner count
        unique_prisoners = self.inmate_return.data_rows.values('prisoner_number').distinct().count()
        
        # Get gender breakdown
        male_count = self.inmate_return.data_rows.filter(sex__iexact='m').count()
        female_count = self.inmate_return.data_rows.filter(sex__iexact='f').count()
        
        # Get offense breakdown
        offense_data = self.inmate_return.data_rows.values('offense').annotate(
            count=models.Count('id')
        ).order_by('-count')[:10]
        
        return {
            'template': template,
            'total_rows': total_rows,
            'unique_prisoners': unique_prisoners,
            'male_count': male_count,
            'female_count': female_count,
            'offense_breakdown': offense_data,
            'return_type': self.inmate_return.get_return_type_display(),
            'station': self.inmate_return.station.name,
            'month': self.inmate_return.get_month_display(),
            'year': self.inmate_return.year,
        }