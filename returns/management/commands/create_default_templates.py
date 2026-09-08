from django.core.management.base import BaseCommand
from returns.models import ReturnTemplate


class Command(BaseCommand):
    help = 'Create default return templates for all 15 categories'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Creating default return templates...'))
        
        # Template definitions for all 15 categories
        templates = [
            {
                'name': 'Convicted Inmates Return',
                'category': 'convicted_inmates',
                'description': 'Monthly return for convicted inmates held at a prison station.',
                'required_columns': [
                    'SER.NO', 'PRIS.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT/CASE.No', 'SENTENCE', 'DATE OF COMMITTAL',
                    'EXPIRY DATE OF RELEASE WITHOUT REMISSION',
                    'EXPIRY DATE OF RELEASE WITH REMISSION'
                ],
                'column_headers': [
                    'SER.NO', 'PRIS.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT/CASE.No', 'SENTENCE', 'DATE OF COMMITTAL',
                    'EXPIRY DATE OF RELEASE WITHOUT REMISSION',
                    'EXPIRY DATE OF RELEASE WITH REMISSION'
                ],
                'example_data': [
                    ['1', 'ZA02/26', 'PATRICK PHIRI', 'V: Khata T/A: Malembo D. Kasungu', 'M', '26',
                     'Theft', 'F.G.M Mulungudzi Zomba 02/25', '72 months', '20-09-2025', '19-09-2031', '19-09-2029'],
                ]
            },
            {
                'name': 'Due Discharge Return',
                'category': 'due_discharge',
                'description': 'Monthly return for prisoners due for discharge.',
                'required_columns': [
                    'S/No', 'PRIS.No', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT/CASE.No', 'SENTENCE', 'DATE OF CONVICTION',
                    'AMNESTY EARNED', 'DUE DATE', 'REMARKS'
                ],
                'column_headers': [
                    'S/No', 'PRIS.No', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT/CASE.No', 'SENTENCE', 'DATE OF CONVICTION',
                    'AMNESTY EARNED', 'DUE DATE', 'REMARKS'
                ],
                'example_data': [
                    ['1', 'ZA02/26', 'PATRICK PHIRI', 'V: Khata T/A: Malembo D. Kasungu', 'M', '26',
                     'Theft', 'F.G.M Mulungudzi Zomba 20/25', '72 months', '20-09-2025', '6 months', '04-04-2029', 'Loss of remission 15 days'],
                ]
            },
            {
                'name': 'Remand Murder Prisoners Return',
                'category': 'remand_murder',
                'description': 'Monthly return for remand murder prisoners.',
                'required_columns': [
                    'Ser.No', 'PRIS.NO', 'NAME', 'PARTICULARS', 'AGE', 'SEX',
                    'OFFENSE', 'COURT/CASE.No', 'DATE OF ADMISSION',
                    'ARRESTING AUTHORITY', 'LAST COURT APPEARANCE',
                    'JUDGE NAME', 'STATUS'
                ],
                'column_headers': [
                    'Ser.No', 'PRIS.NO', 'NAME', 'PARTICULARS', 'AGE', 'SEX',
                    'OFFENSE', 'COURT/CASE.No', 'DATE OF ADMISSION',
                    'ARRESTING AUTHORITY', 'LAST COURT APPEARANCE',
                    'JUDGE NAME', 'STATUS'
                ],
                'example_data': [
                    ['1', 'ZA02/26', 'PATRICK PHIRI', 'V: Khata T/A: Malembo D. Kasungu', '26', 'M',
                     'Murder', 'HIGH COURT ZOMBA 02/25', '20-09-2025', 'Jali Police', '15-10-2025', 'Judge Mwambe', 'Pending'],
                ]
            },
            {
                'name': 'Convicted Foreigners Return',
                'category': 'convicted_foreigners',
                'description': 'Monthly return for convicted foreign nationals.',
                'required_columns': [
                    'SER.NO', 'PRIS.No', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT', 'SENTENCE', 'DATE OF CONVICTION',
                    'AMNESTY EARNED', 'EXPECTED DATE OF RELEASE'
                ],
                'column_headers': [
                    'SER.NO', 'PRIS.No', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT', 'SENTENCE', 'DATE OF CONVICTION',
                    'AMNESTY EARNED', 'EXPECTED DATE OF RELEASE'
                ],
                'example_data': [
                    ['1', 'ZA04/26', 'John Zanda', 'V: P: D: C: Mozambique', 'M', '26',
                     'Theft', 'F.G.M C/No 2/25 Zomba', '72 months', '20-09-2025', 'Nil', '04-10-2029'],
                    ['2', 'ZA22/26', 'Ethel Game', 'V: P: D: C: Zambia', 'F', '26',
                     'Theft', 'F.G.M C/No 230/25 Zomba', '72 months', '02-09-2025', 'Nil', '01-09-2029'],
                ]
            },
            {
                'name': 'General Remandees Return',
                'category': 'general_remand',
                'description': 'Monthly return for general remandees.',
                'required_columns': [
                    'SER.NO', 'PRIS.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT/CASE.No', 'DATE OF ADMISSION',
                    'ARRESTING AUTHORITY', 'LAST COURT APPEARANCE', 'CASE STATUS'
                ],
                'column_headers': [
                    'SER.NO', 'PRIS.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT/CASE.No', 'DATE OF ADMISSION',
                    'ARRESTING AUTHORITY', 'LAST COURT APPEARANCE', 'CASE STATUS'
                ],
                'example_data': [
                    ['1', 'Mzu9/25', 'Tsedeke Girma', 'V: Hosana P: Hosana D: Hosana C: Zambia', 'M', '18',
                     'Illegal Entry', 'SGM C/No 14/25 Euthini', '22-02-2025', 'Kafukule Immigration', '20-03-2025', 'Waiting deportation'],
                    ['2', 'Mzu10/25', 'James Phiri', 'V: Agoni P: Domwe D: Chitungwi C: Zimbabwe', 'M', '20',
                     'Theft', 'FGM C/No 102/25 Mzuzu', '22-02-2025', 'Mzuzu Police', '20-03-2025', 'Waiting for judgement'],
                ]
            },
            {
                'name': 'Pardon Consideration List',
                'category': 'pardon_consideration',
                'description': 'List of convicted prisoners to be considered for pardon.',
                'required_columns': [
                    'NO', 'PRIS.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT', 'SENTENCE', 'DOC', 'SENT WITH REM.',
                    'SENT. SERVED', 'AMNESTY EARNED', 'EXPECTED DATE OF RELEASE',
                    'PARTICULARS OF PREVIOUS CONVICTION', 'CONDUCT'
                ],
                'column_headers': [
                    'NO', 'PRIS.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT', 'SENTENCE', 'DOC', 'SENT WITH REM.',
                    'SENT. SERVED', 'AMNESTY EARNED', 'EXPECTED DATE OF RELEASE',
                    'PARTICULARS OF PREVIOUS CONVICTION', 'CONDUCT'
                ],
                'example_data': [
                    ['1', 'BT 9/25', 'JUSTIN BANDA', 'V: CHIDE T/A: BVUMBWE D: THYOLO', 'M', '24',
                     'THEFT', 'F.G.M C/NO 785/25 MIDIMA', '9 MONTHS IHL', '02-07-2025', '6 MONTHS',
                     '3 MONTHS', '', '01-01-26', 'ONE BURLARY AND THEFT', 'GOOD'],
                ]
            },
            {
                'name': 'Chronically Ill Convicted Inmates',
                'category': 'chronically_ill',
                'description': 'List of chronically ill convicted inmates proposed for pardon.',
                'required_columns': [
                    'NO', 'PRIS.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT', 'SENTENCE', 'DOC', 'SENT WITH REM.',
                    'AMNESTY EARNED', 'EXPECTED DATE OF RELEASE',
                    'PARTICULARS OF PREVIOUS CONVICTION', 'CONDUCT'
                ],
                'column_headers': [
                    'NO', 'PRIS.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT', 'SENTENCE', 'DOC', 'SENT WITH REM.',
                    'AMNESTY EARNED', 'EXPECTED DATE OF RELEASE',
                    'PARTICULARS OF PREVIOUS CONVICTION', 'CONDUCT'
                ],
                'example_data': [
                    ['1', 'BT 9/25', 'JUSTIN BANDA', 'V: CHIDE T/A: BVUMBWE D: THYOLO', 'M', '24',
                     'THEFT', 'F.G.M C/NO 785/25 MIDIMA', '30 MONTHS IHL', '02-07-2023', '20 MONTHS',
                     'TWO-THREE MONTHS', '01-06-2024', 'NIL', 'GOOD'],
                ]
            },
            {
                'name': 'Elderly Inmates (70+)',
                'category': 'elderly_inmates',
                'description': 'List of convicted elderly inmates aged 70 years and above proposed for pardon.',
                'required_columns': [
                    'NO', 'PRIS.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT', 'SENTENCE', 'DOC', 'SENT WITH REM.',
                    'SENT. SERVED', 'AMNESTY EARNED', 'EXPECTED DATE OF RELEASE',
                    'PARTICULARS OF PREVIOUS CONVICTION', 'CONDUCT'
                ],
                'column_headers': [
                    'NO', 'PRIS.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT', 'SENTENCE', 'DOC', 'SENT WITH REM.',
                    'SENT. SERVED', 'AMNESTY EARNED', 'EXPECTED DATE OF RELEASE',
                    'PARTICULARS OF PREVIOUS CONVICTION', 'CONDUCT'
                ],
                'example_data': [
                    ['1', 'BT 9/25', 'JUSTIN BANDA', 'V: CHIDE T/A: BVUMBWE D: THYOLO', 'M', '72',
                     'THEFT', 'F.G.M C/NO 785/25 MIDIMA', '30 MONTHS IHL', '02-07-2023', '20 MONTHS',
                     'TWO-THREE MONTHS', 'SIX MONTHS', '01-06-2024', 'NIL', 'GOOD'],
                ]
            },
            {
                'name': 'Discharged After Reduction',
                'category': 'discharged_reduction',
                'description': 'Return for prisoners discharged after effecting 6 months reduction from their sentences.',
                'required_columns': [
                    'NO', 'PRIS.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT', 'SENTENCE', 'DOC', 'AMNESTY EARNED',
                    'EXPECTED DATE OF RELEASE', 'EDR AFTER AMNESTY'
                ],
                'column_headers': [
                    'NO', 'PRIS.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT', 'SENTENCE', 'DOC', 'AMNESTY EARNED',
                    'EXPECTED DATE OF RELEASE', 'EDR AFTER AMNESTY'
                ],
                'example_data': [
                    ['1', 'BT 9/25', 'JUSTIN BANDA', 'V: CHIDE T/A: BVUMBWE D: THYOLO', 'M', '24',
                     'THEFT', 'F.G.M C/NO 785/25 MIDIMA', '30 MONTHS IHL', '02-07-2023', 'SIX MONTHS',
                     '01-06-2024', '31-12-2023'],
                ]
            },
            {
                'name': 'Children Accompanying Mothers',
                'category': 'children_with_mothers',
                'description': 'Return for children accompanying their mothers in prison.',
                'required_columns': [
                    'S/N', 'PRI.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT CASE NO.', 'SENTENCE', 'DATE OF CONV.',
                    'E.D.R', 'NAME OF A CHILD', 'AGE', 'SEX'
                ],
                'column_headers': [
                    'S/N', 'PRI.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT CASE NO.', 'SENTENCE', 'DATE OF CONV.',
                    'E.D.R', 'NAME OF A CHILD', 'AGE', 'SEX'
                ],
                'example_data': [
                    ['01', 'TO 60/2024', 'ELIZA JOHN', 'V: CHIBWANA T/A: NCHILAMWERA D: THYOLO', 'F', '35',
                     'MURDER U/S 209 of P/C', 'HIGH COURT-BLANTYRE CC/NO.185/2020', '30 YEARS', '07-06-2024',
                     '06-06-2044', 'MIRACLE MUNYENGELA', '13 MONTHS', 'F'],
                ]
            },
            {
                'name': 'Pregnant Convicted Prisoners',
                'category': 'pregnant_convicted',
                'description': 'Return for convicted pregnant prisoners.',
                'required_columns': [
                    'PRIS.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE', 'OFFENSE',
                    'COURT', 'SENTENCE', 'DOC', 'AMNESTY EARNED',
                    'EXPECTED DATE OF RELEASE', 'GESTATION PERIOD', 'REMARKS'
                ],
                'column_headers': [
                    'PRIS.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE', 'OFFENSE',
                    'COURT', 'SENTENCE', 'DOC', 'AMNESTY EARNED',
                    'EXPECTED DATE OF RELEASE', 'GESTATION PERIOD', 'REMARKS'
                ],
                'example_data': [
                    ['BT 9/25', 'JANE BANDA', 'V: CHIDE T/A: BVUMBWE D: THYOLO', 'M', '24',
                     'THEFT', 'F.G.M C/NO 785/25 MIDIMA', '30 MONTHS IHL', '02-07-2023',
                     'TWO-THREE MONTHS', '01-06-2024', '5 MONTHS', ''],
                ]
            },
            {
                'name': 'Pregnant Remand Prisoners',
                'category': 'pregnant_remand',
                'description': 'Return for pregnant remand (murder) prisoners.',
                'required_columns': [
                    'S/N', 'REM.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT/CASE NO.', 'GESTATION PERIOD', 'REMARKS'
                ],
                'column_headers': [
                    'S/N', 'REM.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT/CASE NO.', 'GESTATION PERIOD', 'REMARKS'
                ],
                'example_data': [
                    ['01', '0102/24', 'YASINTA YOHANE', 'V: THABANI T/A: GOVATI D: MWANZA', 'F', '23',
                     'MURDER', 'HIGH COURT CC/NO.18/2025', '7 MONTHS', ''],
                ]
            },
            {
                'name': 'Children with Mothers on Remand',
                'category': 'children_remand',
                'description': 'Return for children accompanying their mothers on homicide and general remand.',
                'required_columns': [
                    'S/N', 'PRI.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT CASE NO.', 'D.O.C', 'NAME OF A CHILD', 'AGE', 'SEX'
                ],
                'column_headers': [
                    'S/N', 'PRI.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT CASE NO.', 'D.O.C', 'NAME OF A CHILD', 'AGE', 'SEX'
                ],
                'example_data': [
                    ['1', 'TO 18/23', 'CHIKOND SAMERA', 'V: MAGOMBO T/A: NCHILAMWERA D: THYOLO', 'F', '22',
                     'MURDER', 'S.G.M THYOLO CC/NO.815/2023', '26-07-2023', 'STANCY MATIAS', '18 MONTHS', 'FEMALE'],
                ]
            },
            {
                'name': 'Foreigners on Remand',
                'category': 'foreigners_remand',
                'description': 'Return for foreign nationals on remand.',
                'required_columns': [
                    'SER.NO', 'PRIS.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT AND CASE NO.', 'DATE OF ADMISSION',
                    'ARRESTING AUTHORITY', 'PRE-TRIAL PERIOD', 'REMARKS'
                ],
                'column_headers': [
                    'SER.NO', 'PRIS.NO', 'NAME', 'PARTICULARS', 'SEX', 'AGE',
                    'OFFENSE', 'COURT AND CASE NO.', 'DATE OF ADMISSION',
                    'ARRESTING AUTHORITY', 'PRE-TRIAL PERIOD', 'REMARKS'
                ],
                'example_data': [
                    ['1', 'Mzu9/25', 'Tsedeke Girma', 'V: Hosana P: Hosana D: Hosana C: Zambia', 'M', '18',
                     'Illegal Entry', 'SGM C/No 14/25 Euthini', '22-02-2025', 'Kafukule Immigration', 'Waiting deportation', ''],
                ]
            },
        ]

        created_count = 0
        updated_count = 0
        
        for template_data in templates:
            # Check if template already exists
            try:
                existing = ReturnTemplate.objects.get(category=template_data['category'])
                # Update existing template
                existing.name = template_data['name']
                existing.description = template_data['description']
                existing.required_columns = template_data['required_columns']
                existing.column_headers = template_data['column_headers']
                existing.example_data = template_data['example_data']
                existing.is_default = True
                existing.is_active = True
                existing.save()
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'Updated template: {template_data["name"]}'))
            except ReturnTemplate.DoesNotExist:
                # Create new template
                ReturnTemplate.objects.create(
                    name=template_data['name'],
                    category=template_data['category'],
                    description=template_data['description'],
                    required_columns=template_data['required_columns'],
                    column_headers=template_data['column_headers'],
                    example_data=template_data['example_data'],
                    is_default=True,
                    is_active=True,
                )
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created template: {template_data["name"]}'))

        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS(f'Created: {created_count} templates'))
        self.stdout.write(self.style.SUCCESS(f'Updated: {updated_count} templates'))
        self.stdout.write(self.style.SUCCESS(f'Total: {created_count + updated_count} templates'))
        self.stdout.write(self.style.SUCCESS('=' * 50))
        
        # Show all templates
        self.stdout.write(self.style.WARNING('\nAll default templates:'))
        templates = ReturnTemplate.objects.filter(is_default=True).order_by('category')
        for template in templates:
            self.stdout.write(f'  - {template.name} ({template.get_category_display()})')