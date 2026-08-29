from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from dateutil.relativedelta import relativedelta
from django.core.validators import MinValueValidator
from django.db.models import Count, Sum
import math
from django.conf import settings
from django.core.exceptions import ValidationError

User = get_user_model()

class PrisonStation(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    location = models.CharField(max_length=100)
    capacity = models.PositiveIntegerField()
    date_established = models.DateField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_stations'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Prison Station"
        verbose_name_plural = "Prison Stations"
        
class Prisoner(models.Model):
    PRISONER_CLASS_CHOICES = [
        ('convicted', 'Convicted'),
        ('remand', 'Remand'),
    ]

    SEX_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]

    prisoner_number = models.CharField(max_length=20, unique=True)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    surname = models.CharField(max_length=100)
    sex = models.CharField(max_length=10, choices=SEX_CHOICES)
    age = models.PositiveIntegerField()
    prisoner_class = models.CharField(max_length=10, choices=PRISONER_CLASS_CHOICES)
    prison_station = models.ForeignKey(PrisonStation, on_delete=models.CASCADE)
    block_number = models.CharField(max_length=10)
    cell_number = models.CharField(max_length=10)
    image = models.ImageField(upload_to='prisoner_images/', blank=True, null=True)
    date_admitted = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    date_released = models.DateField(blank=True, null=True) 
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_prisoners')
    last_modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.prisoner_number} - {self.first_name} {self.surname}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.middle_name} {self.surname}".strip()

class ConvictedPrisoner(models.Model):
    OFFENSE_CHOICES = sorted([ # Sorted alphabetically for better UX
    ('Libel contrary to section 200 of the Penal Code', 'Libel contrary to section 200 of the Penal Code'),
    ('Publication of defamatory matter concerning a dead person without consent contrary to section 201 of the Penal Code', 'Publication of defamatory matter concerning a dead person without consent contrary to section 201 of the Penal Code'),
    ('Manslaughter contrary to section 208 of the Penal Code', 'Manslaughter contrary to section 208 of the Penal Code'),
    ('Murder contrary to section 209 of the Penal Code', 'Murder contrary to section 209 of the Penal Code'),
    ('Accessory after the fact to murder contrary to section 225 of the Penal Code', 'Accessory after the fact to murder contrary to section 225 of the Penal Code'),
    ('Written threats to murder contrary to section 226 of the Penal Code', 'Written threats to murder contrary to section 226 of the Penal Code'),
    ('Conspiracy to murder contrary to section 227 of the Penal Code', 'Conspiracy to murder contrary to section 227 of the Penal Code'),
    ('Aiding suicide contrary to section 228 of the Penal Code', 'Aiding suicide contrary to section 228 of the Penal Code'),
    ('Attempting suicide contrary to section 229 of the Penal Code', 'Attempting suicide contrary to section 229 of the Penal Code'),
    ('Infanticide contrary to section 230 of the Penal Code', 'Infanticide contrary to section 230 of the Penal Code'),
    ('Killing unborn child contrary to section 231 of the Penal Code', 'Killing unborn child contrary to section 231 of the Penal Code'),
    ('Concealing birth of child contrary to section 232 of the Penal Code', 'Concealing birth of child contrary to section 232 of the Penal Code'),
    ('Abandonment of child at birth contrary to section 232A of the Penal Code', 'Abandonment of child at birth contrary to section 232A of the Penal Code'),
    ('Genocide contrary to section 217A of the Penal Code', 'Genocide contrary to section 217A of the Penal Code'),
    ('Disabling to commit felony/misdemeanor contrary to section 233 of the Penal Code', 'Disabling to commit felony/misdemeanor contrary to section 233 of the Penal Code'),
    ('Stupefying to commit felony/misdemeanor contrary to section 234 of the Penal Code', 'Stupefying to commit felony/misdemeanor contrary to section 234 of the Penal Code'),
    ('Acts intended to cause grievous harm or prevent arrest contrary to section 235 of the Penal Code', 'Acts intended to cause grievous harm or prevent arrest contrary to section 235 of the Penal Code'),
    ('Preventing escape from wreck contrary to section 236 of the Penal Code', 'Preventing escape from wreck contrary to section 236 of the Penal Code'),
    ('Endangering safety of persons traveling by railway/road contrary to section 237 of the Penal Code', 'Endangering safety of persons traveling by railway/road contrary to section 237 of the Penal Code'),
    ('Grievous harm contrary to section 238 of the Penal Code', 'Grievous harm contrary to section 238 of the Penal Code'),
    ('Attempting to injure by explosives contrary to section 239 of the Penal Code', 'Attempting to injure by explosives contrary to section 239 of the Penal Code'),
    ('Administering poison with intent to harm contrary to section 240 of the Penal Code', 'Administering poison with intent to harm contrary to section 240 of the Penal Code'),
    ('Wounding contrary to section 241 of the Penal Code', 'Wounding contrary to section 241 of the Penal Code'),
    ('Failure to supply necessaries contrary to section 242 of the Penal Code', 'Failure to supply necessaries contrary to section 242 of the Penal Code'),
    ('Criminal trespass contrary to section 314 of the Penal Code', 'Criminal trespass contrary to section 314 of the Penal Code'),
    ('Kidnapping from Malawi contrary to section 260 of the Penal Code', 'Kidnapping from Malawi contrary to section 260 of the Penal Code'),
    ('Kidnapping or abducting to murder contrary to section 261 of the Penal Code', 'Kidnapping or abducting to murder contrary to section 261 of the Penal Code'),
    ('Kidnapping or abducting to confine person contrary to section 262 of the Penal Code', 'Kidnapping or abducting to confine person contrary to section 262 of the Penal Code'),
    ('Kidnapping or abducting for grievous harm, ransom, slavery, etc. contrary to section 263 of the Penal Code', 'Kidnapping or abducting for grievous harm, ransom, slavery, etc. contrary to section 263 of the Penal Code'),
    ('Wrongfully concealing or confining kidnapped/abducted person contrary to section 264 of the Penal Code', 'Wrongfully concealing or confining kidnapped/abducted person contrary to section 264 of the Penal Code'),
    ('Kidnapping child under 16 to steal property contrary to section 265 of the Penal Code', 'Kidnapping child under 16 to steal property contrary to section 265 of the Penal Code'),
    ('Buying or disposing of a person as a slave contrary to section 267 of the Penal Code', 'Buying or disposing of a person as a slave contrary to section 267 of the Penal Code'),
    ('Habitual dealing in slaves contrary to section 268 of the Penal Code', 'Habitual dealing in slaves contrary to section 268 of the Penal Code'),
    ('Unlawful compulsory labour contrary to section 269 of the Penal Code', 'Unlawful compulsory labour contrary to section 269 of the Penal Code'),
    ('Theft contrary to section 278 of the Penal Code', 'Theft contrary to section 278 of the Penal Code'),
    ('Stealing wills contrary to section 279 of the Penal Code', 'Stealing wills contrary to section 279 of the Penal Code'),
    ('Stealing postal matter contrary to section 280 of the Penal Code', 'Stealing postal matter contrary to section 280 of the Penal Code'),
    ('Stealing cattle contrary to section 281 of the Penal Code', 'Stealing cattle contrary to section 281 of the Penal Code'),
    ('Stealing from the person/goods in transit contrary to section 282 of the Penal Code', 'Stealing from the person/goods in transit contrary to section 282 of the Penal Code'),
    ('Stealing by persons in public service contrary to section 283 of the Penal Code', 'Stealing by persons in public service contrary to section 283 of the Penal Code'),
    ('Robbery contrary to section 300 of the Penal Code', 'Robbery contrary to section 300 of the Penal Code'),
    ('Attempted robbery contrary to section 302 of the Penal Code', 'Attempted robbery contrary to section 302 of the Penal Code'),
    ('Assault with intent to steal contrary to section 303 of the Penal Code', 'Assault with intent to steal contrary to section 303 of the Penal Code'),
    ('Demanding property by written threats contrary to section 304 of the Penal Code', 'Demanding property by written threats contrary to section 304 of the Penal Code'),
    ('Burglary/housebreaking contrary to section 309 of the Penal Code', 'Burglary/housebreaking contrary to section 309 of the Penal Code'),
    ('Breaking into building and committing felony contrary to section 311 of the Penal Code', 'Breaking into building and committing felony contrary to section 311 of the Penal Code'),
    ('Possession of housebreaking instruments contrary to section 313 of the Penal Code', 'Possession of housebreaking instruments contrary to section 313 of the Penal Code'),
    ('Arson contrary to section 337 of the Penal Code', 'Arson contrary to section 337 of the Penal Code'),
    ('Attempted arson contrary to section 338 of the Penal Code', 'Attempted arson contrary to section 338 of the Penal Code'),
    ('Forgery contrary to section 356 of the Penal Code', 'Forgery contrary to section 356 of the Penal Code'),
    ('Uttering false document contrary to section 360 of the Penal Code', 'Uttering false document contrary to section 360 of the Penal Code'),
    ('Counterfeiting coin contrary to section 372 of the Penal Code', 'Counterfeiting coin contrary to section 372 of the Penal Code'),
    ('Clipping coin contrary to section 375 of the Penal Code', 'Clipping coin contrary to section 375 of the Penal Code'),
    ('Uttering counterfeit coin contrary to section 379 of the Penal Code', 'Uttering counterfeit coin contrary to section 379 of the Penal Code'),
    ('Corrupt practices (secret commissions) contrary to section 396 of the Penal Code', 'Corrupt practices (secret commissions) contrary to section 396 of the Penal Code'),
    ('Conspiracy to commit felony contrary to section 404 of the Penal Code', 'Conspiracy to commit felony contrary to section 404 of the Penal Code'),
    ('Conspiracy to commit misdemeanor contrary to section 405 of the Penal Code', 'Conspiracy to commit misdemeanor contrary to section 405 of the Penal Code'),
    ('Accessory after the fact to felony contrary to section 408 of the Penal Code', 'Accessory after the fact to felony contrary to section 408 of the Penal Code'),
    ('Money laundering contrary to section 331A of the Penal Code', 'Money laundering contrary to section 331A of the Penal Code'),
    ('Fraudulent appropriation of power/water/telecommunication services contrary to sections 298, 298A, and 298B of the Penal Code', 'Fraudulent appropriation of power/water/telecommunication services contrary to sections 298, 298A, and 298B of the Penal Code'),
    ('Endangering the environment contrary to section 245A of the Penal Code', 'Endangering the environment contrary to section 245A of the Penal Code'),
    ('Criminal recklessness and negligence contrary to sections 246–252 of the Penal Code', 'Criminal recklessness and negligence contrary to sections 246–252 of the Penal Code'),
    ('Common assault contrary to section 253 of the Penal Code', 'Common assault contrary to section 253 of the Penal Code'),
    ('Assault occasioning actual bodily harm contrary to section 254 of the Penal Code', 'Assault occasioning actual bodily harm contrary to section 254 of the Penal Code'),
    ('Assaults on persons protecting wreck contrary to section 255 of the Penal Code', 'Assaults on persons protecting wreck contrary to section 255 of the Penal Code'),
    ('Unauthorized use of land premises contrary to section 316 of the Penal Code', 'Unauthorized use of land premises contrary to section 316 of the Penal Code'),
    ('Fraudulent trading by a company contrary to section 336A of the Penal Code', 'Fraudulent trading by a company contrary to section 336A of the Penal Code'),
    ('Fraud other than false pretence contrary to section 319A of the Penal Code', 'Fraud other than false pretence contrary to section 319A of the Penal Code'),
    ('Evasion of liability by false pretence contrary to section 319B of the Penal Code', 'Evasion of liability by false pretence contrary to section 319B of the Penal Code'),
    ('Making off without payment contrary to section 319C of the Penal Code', 'Making off without payment contrary to section 319C of the Penal Code'),
    ('Passing valueless cheque contrary to section 319D of the Penal Code', 'Passing valueless cheque contrary to section 319D of the Penal Code'),
    ('Receiving stolen property contrary to section 328 of the Penal Code', 'Receiving stolen property contrary to section 328 of the Penal Code'),
    ('Unlawful use of vehicles/animals contrary to section 299 of the Penal Code', 'Unlawful use of vehicles/animals contrary to section 299 of the Penal Code'),
    ('Threatening to burn/destroy property contrary to section 350 of the Penal Code', 'Threatening to burn/destroy property contrary to section 350 of the Penal Code'),
    ('False statements for registers of births, deaths, and marriages contrary to section 370 of the Penal Code', 'False statements for registers of births, deaths, and marriages contrary to section 370 of the Penal Code'),
    ('Personation contrary to section 389 of the Penal Code', 'Personation contrary to section 389 of the Penal Code'),
    ('Counterfeiting trade marks contrary to section 388 of the Penal Code', 'Counterfeiting trade marks contrary to section 388 of the Penal Code'),
    ('Falsifying warrants for money payable under public authority contrary to section 367 of the Penal Code', 'Falsifying warrants for money payable under public authority contrary to section 367 of the Penal Code'),
    ('Wilful damage to survey/boundary marks contrary to section 348 of the Penal Code', 'Wilful damage to survey/boundary marks contrary to section 348 of the Penal Code'),
    ('Exhibition of false light/mark/buoy contrary to section 250 of the Penal Code', 'Exhibition of false light/mark/buoy contrary to section 250 of the Penal Code'),
    ('Treason contrary to section 38', 'Treason contrary to section 38'),
    ('Concealment of treason contrary to section 39', 'Concealment of treason contrary to section 39'),
    ('Promoting war among groups contrary to section 40', 'Promoting war among groups contrary to section 40'),
    ('Inciting to mutiny contrary to section 41', 'Inciting to mutiny contrary to section 41'),
    ('Aiding soldiers/policemen in acts of mutiny contrary to section 42', 'Aiding soldiers/policemen in acts of mutiny contrary to section 42'),
    ('Inducing soldiers/policemen to desert contrary to section 43', 'Inducing soldiers/policemen to desert contrary to section 43'),
    ('Aiding prisoners of war to escape contrary to section 44', 'Aiding prisoners of war to escape contrary to section 44'),
    ('Seditious offenses contrary to section 51', 'Seditious offenses contrary to section 51'),
    ('Unlawful oaths to commit capital offenses contrary to section 54', 'Unlawful oaths to commit capital offenses contrary to section 54'),
    ('Other unlawful oaths to commit offenses contrary to section 55', 'Other unlawful oaths to commit offenses contrary to section 55'),
    ('Compelling another to take an oath contrary to section 56', 'Compelling another to take an oath contrary to section 56'),
    ('Unlawful drilling contrary to section 59', 'Unlawful drilling contrary to section 59'),
    ('Publication of false news contrary to section 60', 'Publication of false news contrary to section 60'),
    ('Defamation of foreign dignitaries contrary to section 61', 'Defamation of foreign dignitaries contrary to section 61'),
    ('Foreign enlistment contrary to section 62', 'Foreign enlistment contrary to section 62'),
    ('Piracy contrary to section 63', 'Piracy contrary to section 63'),
    ('Managing an unlawful society contrary to section 65', 'Managing an unlawful society contrary to section 65'),
    ('Being a member of an unlawful society contrary to section 66', 'Being a member of an unlawful society contrary to section 66'),
    ('Unlawful assembly contrary to section 71', 'Unlawful assembly contrary to section 71'),
    ('Riot contrary to section 73', 'Riot contrary to section 73'),
    ('Rioters demolishing buildings contrary to section 78', 'Rioters demolishing buildings contrary to section 78'),
    ('Rioters injuring property contrary to section 79', 'Rioters injuring property contrary to section 79'),
    ('Carrying offensive weapons contrary to section 81', 'Carrying offensive weapons contrary to section 81'),
    ('Forcible entry contrary to section 82', 'Forcible entry contrary to section 82'),
    ('Forcible detainer contrary to section 83', 'Forcible detainer contrary to section 83'),
    ('Fighting in public contrary to section 84', 'Fighting in public contrary to section 84'),
    ('Threatening violence contrary to section 86', 'Threatening violence contrary to section 86'),
    ('Proposing violence at assemblies contrary to section 87', 'Proposing violence at assemblies contrary to section 87'),
    ('Intimidation contrary to section 88', 'Intimidation contrary to section 88'),
    ('Assembling for smuggling contrary to section 89', 'Assembling for smuggling contrary to section 89'),
    ('Official corruption contrary to section 90', 'Official corruption contrary to section 90'),
    ('Extortion by public officers contrary to section 91', 'Extortion by public officers contrary to section 91'),
    ('Public officers receiving property to show favor contrary to section 92', 'Public officers receiving property to show favor contrary to section 92'),
    ('False claims by officials contrary to section 94', 'False claims by officials contrary to section 94'),
    ('Abuse of office contrary to section 95', 'Abuse of office contrary to section 95'),
    ('False certificates by public officers contrary to section 96', 'False certificates by public officers contrary to section 96'),
    ('Unauthorized administration of oaths contrary to section 97', 'Unauthorized administration of oaths contrary to section 97'),
    ('False assumption of authority contrary to section 98', 'False assumption of authority contrary to section 98'),
    ('Personating public officers contrary to section 99', 'Personating public officers contrary to section 99'),
    ('Threat of injury to public servants contrary to section 100', 'Threat of injury to public servants contrary to section 100'),
    ('Perjury contrary to section 101', 'Perjury contrary to section 101'),
    ('Subornation of perjury contrary to section 101(3)', 'Subornation of perjury contrary to section 101(3)'),
    ('Fabricating evidence contrary to section 105', 'Fabricating evidence contrary to section 105'),
    ('False swearing contrary to section 106', 'False swearing contrary to section 106'),
    ('Destroying evidence contrary to section 108', 'Destroying evidence contrary to section 108'),
    ('Conspiracy to defeat justice contrary to section 109', 'Conspiracy to defeat justice contrary to section 109'),
    ('Compounding felonies contrary to section 110', 'Compounding felonies contrary to section 110'),
    ('Advertisements for stolen property contrary to section 112', 'Advertisements for stolen property contrary to section 112'),
    ('Rescue contrary to section 114', 'Rescue contrary to section 114'),
    ('Escape from custody contrary to section 115', 'Escape from custody contrary to section 115'),
    ('Permitting prisoners to escape contrary to section 116', 'Permitting prisoners to escape contrary to section 116'),
    ('Aiding prisoners to escape contrary to section 117', 'Aiding prisoners to escape contrary to section 117'),
    ('Frauds by public officers contrary to section 120', 'Frauds by public officers contrary to section 120'),
    ('Neglect of official duty contrary to section 121', 'Neglect of official duty contrary to section 121'),
    ('False information to public servants contrary to section 122', 'False information to public servants contrary to section 122'),
    ('Disobedience of statutory duty contrary to section 123', 'Disobedience of statutory duty contrary to section 123'),
    ('Soliciting to break the law contrary to section 124', 'Soliciting to break the law contrary to section 124'),
    ('Soliciting public officers to fail duties contrary to section 125', 'Soliciting public officers to fail duties contrary to section 125'),
    ('Insult to religion contrary to section 127', 'Insult to religion contrary to section 127'),
    ('Disturbing religious assemblies contrary to section 128', 'Disturbing religious assemblies contrary to section 128'),
    ('Trespassing on burial places contrary to section 129', 'Trespassing on burial places contrary to section 129'),
    ('Wounding religious feelings contrary to section 130', 'Wounding religious feelings contrary to section 130'),
    ('Hindering burial of a body contrary to section 131', 'Hindering burial of a body contrary to section 131'),
    ('Rape contrary to section 132', 'Rape contrary to section 132'),
    ('Attempted rape contrary to section 134', 'Attempted rape contrary to section 134'),
    ('Abduction contrary to section 135', 'Abduction contrary to section 135'),
    ('Abduction of girls under 16 contrary to section 136', 'Abduction of girls under 16 contrary to section 136'),
    ('Indecent assault on females contrary to section 137', 'Indecent assault on females contrary to section 137'),
    ('Indecent practices between females contrary to section 137A', 'Indecent practices between females contrary to section 137A'),
    ('Defilement of girls under 16 contrary to section 138', 'Defilement of girls under 16 contrary to section 138'),
    ('Defilement of idiots/imbeciles contrary to section 139', 'Defilement of idiots/imbeciles contrary to section 139'),
    ('Procuration contrary to section 140', 'Procuration contrary to section 140'),
    ('Procuring defilement by threats/fraud contrary to section 141', 'Procuring defilement by threats/fraud contrary to section 141'),
    ('Permitting defilement on premises contrary to section 142', 'Permitting defilement on premises contrary to section 142'),
    ('Detention in a brothel contrary to section 143', 'Detention in a brothel contrary to section 143'),
    ('Living on earnings of prostitution contrary to section 145', 'Living on earnings of prostitution contrary to section 145'),
    ('Aiding prostitution contrary to section 146', 'Aiding prostitution contrary to section 146'),
    ('Keeping a brothel contrary to section 147', 'Keeping a brothel contrary to section 147'),
    ('Promoting prostitution contrary to section 147A', 'Promoting prostitution contrary to section 147A'),
    ('Conspiracy to defile contrary to section 148', 'Conspiracy to defile contrary to section 148'),
    ('Attempting to procure abortion contrary to section 149', 'Attempting to procure abortion contrary to section 149'),
    ('Self-abortion by a pregnant woman contrary to section 150', 'Self-abortion by a pregnant woman contrary to section 150'),
    ('Supplying abortion drugs/instruments contrary to section 151', 'Supplying abortion drugs/instruments contrary to section 151'),
    ('Unnatural offenses contrary to section 153', 'Unnatural offenses contrary to section 153'),
    ('Attempted unnatural offenses contrary to section 154', 'Attempted unnatural offenses contrary to section 154'),
    ('Indecent assault on boys under 14 contrary to section 155', 'Indecent assault on boys under 14 contrary to section 155'),
    ('Indecent assault on idiots/imbeciles contrary to section 155A', 'Indecent assault on idiots/imbeciles contrary to section 155A'),
    ('Indecent practices between males contrary to section 156', 'Indecent practices between males contrary to section 156'),
    ('Incest by males contrary to section 157', 'Incest by males contrary to section 157'),
    ('Incest by females contrary to section 158', 'Incest by females contrary to section 158'),
    ('Sexual intercourse with minors under care contrary to section 159A', 'Sexual intercourse with minors under care contrary to section 159A'),
    ('Sexual activity with a child contrary to section 160B', 'Sexual activity with a child contrary to section 160B'),
    ('Indecent practice with a child contrary to section 160C', 'Indecent practice with a child contrary to section 160C'),
    ('Exposing offensive material to a child contrary to section 160D', 'Exposing offensive material to a child contrary to section 160D'),
    ('Recording a child in prohibited acts contrary to section 160E', 'Recording a child in prohibited acts contrary to section 160E'),
    ('Procuring child for harmful entertainment contrary to section 160F', 'Procuring child for harmful entertainment contrary to section 160F'),
    ('Fraudulent pretence of marriage contrary to section 161', 'Fraudulent pretence of marriage contrary to section 161'),
    ('Bigamy contrary to section 162', 'Bigamy contrary to section 162'),
    ('Marriage ceremony fraud contrary to section 163', 'Marriage ceremony fraud contrary to section 163'),
    ('Desertion of children contrary to section 164', 'Desertion of children contrary to section 164'),
    ('Neglecting to provide for children contrary to section 165', 'Neglecting to provide for children contrary to section 165'),
    ('Child stealing contrary to section 167', 'Child stealing contrary to section 167'),
    ('Common nuisance contrary to section 168', 'Common nuisance contrary to section 168'),
    ('Keeping a gaming house contrary to section 169', 'Keeping a gaming house contrary to section 169'),
    ('Betting house offenses contrary to section 170', 'Betting house offenses contrary to section 170'),
    ('Organizing/managing pools contrary to section 176', 'Organizing/managing pools contrary to section 176'),
    ('Chain letters contrary to section 177', 'Chain letters contrary to section 177'),
    ('Obscene materials contrary to section 179', 'Obscene materials contrary to section 179'),
    ('Idle and disorderly conduct contrary to section 180', 'Idle and disorderly conduct contrary to section 180'),
    ('Conduct likely to breach peace contrary to section 181', 'Conduct likely to breach peace contrary to section 181'),
    ('Insulting language contrary to section 182', 'Insulting language contrary to section 182'),
    ('Drunkenness offenses contrary to section 183', 'Drunkenness offenses contrary to section 183'),
    ('Rogues and vagabonds contrary to section 184', 'Rogues and vagabonds contrary to section 184'),
    ('Wearing uniform without authority contrary to section 191', 'Wearing uniform without authority contrary to section 191'),
    ('Negligent spread of disease contrary to section 192', 'Negligent spread of disease contrary to section 192'),
    ('Adulteration of food/drink contrary to sections 193, 193A', 'Adulteration of food/drink contrary to sections 193, 193A'),
    ('Sale of noxious food/drink contrary to section 194', 'Sale of noxious food/drink contrary to section 194'),
    ('Adulteration/sale of drugs contrary to sections 195, 195A, 196', 'Adulteration/sale of drugs contrary to sections 195, 195A, 196'),
    ('Fouling water/air contrary to sections 197, 198', 'Fouling water/air contrary to sections 197, 198'),
    ('Libel contrary to section 200', 'Libel contrary to section 200'),
    ('Attempted murder contrary to section 223', 'Attempted murder contrary to section 223'),
    ('Reckless/negligent acts contrary to section 246', 'Reckless/negligent acts contrary to section 246'),
    ('Assault occasioning bodily harm contrary to section 254', 'Assault occasioning bodily harm contrary to section 254'),
    ('Kidnapping from lawful guardianship contrary to section 258', 'Kidnapping from lawful guardianship contrary to section 258'),
    ('Felling or damaging trees in forest reserves contrary to section 64 of the Forestry Act','Felling or damaging trees in forest reserves contrary to section 64 of the Forestry Act'),
    ('Unauthorized fires in forest areas contrary to section 65 of the Forestry Act','Unauthorized fires in forest areas contrary to section 65 of the Forestry Act'),
    ('Harming wildlife or collecting eggs contrary to section 66 of the Forestry Act','Harming wildlife or collecting eggs contrary to section 66 of the Forestry Act'),
    ('Violating pest and disease control rules contrary to section 67 of the Forestry Act','Violating pest and disease control rules contrary to section 67 of the Forestry Act'),
    ('Illegal possession or trafficking of forest produce contrary to section 68 of the Forestry Act','Illegal possession or trafficking of forest produce contrary to section 68 of the Forestry Act'),
    ('Obstructing forestry officers contrary to section 69 of the Forestry Act','Obstructing forestry officers contrary to section 69 of the Forestry Act'),
    ('Forging or altering forestry documents contrary to section 70 of the Forestry Act','Forging or altering forestry documents contrary to section 70 of the Forestry Act'),
    ('Possessing weapons or traps in forest reserves contrary to section 71 of the Forestry Act','Possessing weapons or traps in forest reserves contrary to section 71 of the Forestry Act'),
    ('Illegal dumping of litter or waste contrary to section 72 of the Forestry Act','Illegal dumping of litter or waste contrary to section 72 of the Forestry Act'),
    ('Smuggling forest produce (import/export without permit) contrary to section 73 of the Forestry Act','Smuggling forest produce (import/export without permit) contrary to section 73 of the Forestry Act'),
    ('Unauthorized charcoal production contrary to section 81 of the Forestry Act','Unauthorized charcoal production contrary to section 81 of the Forestry Act'),
    ('Operating wood processing industries without permit contrary to section 82 of the Forestry Act','Operating wood processing industries without permit contrary to section 82 of the Forestry Act'),
    ('Illegal removal of indigenous timber from private land contrary to section 83 of the Forestry Act', 'Illegal removal of indigenous timber from private land contrary to section 83 of the Forestry Act'),
    ('Other', 'Other'),
    ])

    prisoner = models.OneToOneField(Prisoner, on_delete=models.CASCADE, primary_key=True, related_name='convicted_details')
    sentence = models.FloatField(validators=[MinValueValidator(1)], help_text="Sentence in months")
    court = models.CharField(max_length=100)
    offense = models.CharField(max_length=150, choices=OFFENSE_CHOICES, blank=True, null=True)
    date_of_committal = models.DateField()
    wef_date = models.DateField(verbose_name="With Effect From Date")
    date_of_release = models.DateField(blank=True, null=True)
    date_of_release_on_remission = models.DateField(blank=True, null=True)
    confirmation_status = models.BooleanField(default=False)
    notes = models.CharField(blank=True) # Consider models.TextField if notes can be long
    reduction_months = models.FloatField(default=0, blank=True, validators=[MinValueValidator(0)])
    reduction_notes = models.CharField(blank=True) # Consider models.TextField

    def save(self, *args, **kwargs):
        AVG_DAYS_PER_MONTH = 30.4375
        if self.wef_date and self.sentence:
            adjusted_wef = self.wef_date - relativedelta(days=1)
            sentence_months_val = int(self.sentence)
            sentence_fraction = self.sentence - sentence_months_val
            sentence_days = int(sentence_fraction * AVG_DAYS_PER_MONTH)
            self.date_of_release = adjusted_wef + relativedelta(months=sentence_months_val, days=sentence_days)

        if self.date_of_release: # Must be calculated first
            remission_months_total = self.sentence / 3
            remission_months_val = int(remission_months_total)
            remission_fraction = remission_months_total - remission_months_val
            remission_days = int(remission_fraction * AVG_DAYS_PER_MONTH)
            self.date_of_release_on_remission = self.date_of_release - relativedelta(months=remission_months_val, days=remission_days)

        if self.reduction_months and self.reduction_months > 0 and self.date_of_release_on_remission:
            reduction_months_val = int(self.reduction_months)
            reduction_fraction = self.reduction_months - reduction_months_val
            reduction_days = int(reduction_fraction * AVG_DAYS_PER_MONTH)
            self.date_of_release_on_remission -= relativedelta(months=reduction_months_val, days=reduction_days)
        super().save(*args, **kwargs)

class RemandPrisoner(models.Model):
    OFFENSE_CHOICES = ConvictedPrisoner.OFFENSE_CHOICES # Use the same choices

    prisoner = models.OneToOneField(Prisoner, on_delete=models.CASCADE, primary_key=True, related_name='remand_details')
    court_case_number = models.CharField(max_length=50)
    next_court_date = models.DateField()
    remand_extensions = models.PositiveIntegerField(default=0)
    offense = models.CharField(max_length=150, choices=OFFENSE_CHOICES, blank=True, null=True)

    def __str__(self):
        return f"{self.prisoner.prisoner_number} - {self.court_case_number}"

class RiskAssessment(models.Model):
    RISK_LEVEL_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
        ('need_support', 'Need Support'),
    ]

    prisoner = models.OneToOneField(Prisoner, on_delete=models.CASCADE, primary_key=True, related_name='risk_assessment')
    previous_conviction = models.BooleanField(default=False)
    previous_convictions_count = models.PositiveIntegerField(default=0)
    risk_level = models.CharField(max_length=20, choices=RISK_LEVEL_CHOICES)

    def __str__(self):
        return f"Risk Assessment for {self.prisoner.prisoner_number}"

class PrisonerParticulars(models.Model):
    NATIONALITY_CHOICES = [
        ('malawian', 'Malawian'),
        ('mozambican', 'Mozambican'),
        ('zimbabwean', 'Zimbabwean'),
        ('congolese', 'Congolese'),
        ('zambian', 'Zambian'),
        ('tanzanian', 'Tanzanian'),
        ('chinese', 'Chinese'),
        ('japanese', 'Japanese'),
        ('korean', 'Korean'),
        ('indian', 'Indian'),
        ('british', 'British'),
        ('south_african', 'South African'),
        ('burundi', 'Burundi'),
        ('rwandan', 'Rwandan'),
        ('botswana', 'Botswana'),
         ('other', 'Other'), # Added 'Other'
    ]

    RELIGION_CHOICES = [
        ('christian', 'Christian'),
        ('muslim', 'Muslim'),
        ('other', 'Other'),
    ]

    EDUCATION_LEVEL_CHOICES = [
        ('none', 'No formal education'),
        ('primary', 'Primary'),
        ('secondary', 'Secondary'),
        ('tertiary', 'Tertiary'),
    ]

    prisoner = models.OneToOneField(Prisoner, on_delete=models.CASCADE, primary_key=True, related_name='particulars')
    nationality = models.CharField(max_length=20, choices=NATIONALITY_CHOICES)
    district = models.CharField(max_length=100)
    chief = models.CharField(max_length=100)
    village = models.CharField(max_length=100)
    home_location = models.CharField(max_length=200, blank=True)
    religion = models.CharField(max_length=20, choices=RELIGION_CHOICES)
    denomination = models.CharField(max_length=100, blank=True)
    fathers_name = models.CharField(max_length=200)
    mothers_name = models.CharField(max_length=200)
    married = models.BooleanField(default=False)
    spouse_name = models.CharField(max_length=200, blank=True)
    spouse_location = models.CharField(max_length=300, blank=True)
    next_of_kin = models.CharField(max_length=200)
    next_of_kin_location = models.CharField(max_length=300)
    mobile_number = models.CharField(max_length=20, blank=True)
    national_id = models.CharField(max_length=50, blank=True)
    passport_number = models.CharField(max_length=50, blank=True)
    driving_license = models.CharField(max_length=50, blank=True)
    education_level = models.CharField(max_length=20, choices=EDUCATION_LEVEL_CHOICES)
    literate = models.BooleanField(default=False)
    profession = models.CharField(max_length=100, blank=True)
    past_occupation = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Particulars for {self.prisoner.prisoner_number}"

class PhysicalCharacteristics(models.Model):
    BODY_BUILD_CHOICES = [
        ('medium', 'Medium body build'),
        ('slim', 'Slim body build'),
        ('fat', 'Fat'),
        ('muscular', 'Muscular'),
        ('heavy', 'Heavy'),
    ]

    SKIN_COLOR_CHOICES = [
        ('light', 'Light in Complexion'),
        ('dark', 'Dark in complexion'),
        ('brown', 'Brown in Complexion'),
        ('albino', 'Albino'),
    ]

    EYES_COLOR_CHOICES = [
        ('brown', 'Brown'),
        ('black', 'Black'),
        ('blue', 'Blue'),
        ('green', 'Green'),
        ('other', 'Other'), # Added 'Other'
    ]

    HEALTH_CHOICES = [
        ('none', 'None'),
        ('tb', 'TB'),
        ('hiv', 'HIV'),
        ('malaria', 'Malaria prone'),
        ('ptsd', 'PTSD'),
        ('stis', 'STIs'),
        ('malnutrition', 'Malnutrition'),
        ('other', 'Other'), # Added 'Other'
    ]

    prisoner = models.OneToOneField(Prisoner, on_delete=models.CASCADE, primary_key=True, related_name='physical')
    height = models.DecimalField(max_digits=5, decimal_places=2, help_text="Height in cm")
    weight = models.DecimalField(max_digits=5, decimal_places=2, help_text="Weight in kg")
    body_build = models.CharField(max_length=20, choices=BODY_BUILD_CHOICES)
    skin_color = models.CharField(max_length=20, choices=SKIN_COLOR_CHOICES)
    eyes_color = models.CharField(max_length=20, choices=EYES_COLOR_CHOICES)
    head_abnormalities = models.CharField(max_length=100, blank=True) # Consider TextField
    health_status = models.CharField(max_length=20, choices=HEALTH_CHOICES, default='none')
    circumcised = models.BooleanField(default=False)
    marks_tattoos_scars = models.CharField(blank=True, max_length=255) # Consider TextField, increased max_length
    has_child = models.BooleanField(default=False)
    children_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Physical Characteristics for {self.prisoner.prisoner_number}"

class RehabilitationProgram(models.Model):
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('expert', 'Expert'),
        ('not_applicable', 'Not Applicable'), # Added
    ]

    prisoner = models.OneToOneField(Prisoner, on_delete=models.CASCADE, primary_key=True, related_name='rehabilitation')
    employed_in_program = models.BooleanField(default=False)
    program_name = models.CharField(max_length=200, blank=True)
    program_level = models.CharField(max_length=20, choices=LEVEL_CHOICES, blank=True)

    def __str__(self):
        return f"Rehabilitation for {self.prisoner.prisoner_number}"

class PrisonerTransfer(models.Model):
    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE, related_name='transfers')
    from_prison = models.ForeignKey(PrisonStation, on_delete=models.CASCADE, related_name='transfers_out')
    to_prison = models.ForeignKey(PrisonStation, on_delete=models.CASCADE, related_name='transfers_in')
    transfer_date = models.DateField(default=timezone.now)
    reason = models.TextField()
    transferred_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Transfer of {self.prisoner.prisoner_number} from {self.from_prison} to {self.to_prison}"

class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('transfer', 'Transfer'),
        ('approve', 'Approve'), # Added for visitor approval etc.
        ('login', 'Login'),   # Example, if you log logins
        ('logout', 'Logout'), # Example
        ('add_item', 'Add Item'), # New action
        ('withdraw_money', 'Withdraw Money'), # New action
        ('collect_item', 'Collect Item'), # New action
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model = models.CharField(max_length=50) # e.g., 'Prisoner', 'Visitor'
    object_id = models.PositiveIntegerField(null=True, blank=True) # Can be null if action is general
    details = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user} {self.action}d {self.model} {self.object_id or ''} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

class ReleaseOnRemission(models.Model):
    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE) # Should this be OneToOne if only one such record per prisoner?
    release_date = models.DateField()
    original_sentence = models.FloatField() # Changed from PositiveIntegerField to match ConvictedPrisoner.sentence
    remission_months = models.DecimalField(max_digits=5, decimal_places=2)
    reduction_months = models.FloatField(default=0) # Changed from PositiveIntegerField
    reduction_reason = models.TextField(blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    processed_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Release on remission for {self.prisoner.prisoner_number}"

class Visitor(models.Model):
    RELATIONSHIP_CHOICES = [
        ('family', 'Family Member'),
        ('friend', 'Friend'),
        ('lawyer', 'Lawyer'),
        ('official', 'Government Official'),
        ('other', 'Other'),
    ]

    ID_TYPE_CHOICES = [ # You might still want to add this if you record ID type
        ('national_id', 'National ID'),
        ('passport', 'Passport'),
        ('drivers_license', 'Driver\'s License'),
        ('other', 'Other'),
    ]

    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=50)
    surname = models.CharField(max_length=50)
    
    # Fields from previous suggestions (now confirmed by screenshot where applicable)
    contact_number = models.CharField(max_length=20, blank=True, null=True) # Matches "Contact Number"
    
    # New fields identified from the screenshot:
    id_number = models.CharField(max_length=50, blank=True, null=True) # Corresponds to "ID Number"
    address = models.TextField(blank=True, null=True) # Corresponds to "Address"
    purpose_of_visit = models.TextField(blank=True, null=True) # Corresponds to "Purpose of Visit"

    # You might consider adding identification_type as well, for context to id_number
    # identification_type = models.CharField(max_length=20, choices=ID_TYPE_CHOICES, blank=True, null=True) 

    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES)
    visit_date = models.DateField()
    visit_time = models.TimeField()
    location = models.CharField(max_length=200, blank=True)
    items = models.CharField(max_length=200, blank=True)
    is_approved = models.BooleanField(default=False)
    denial_reason = models.TextField(blank=True, null=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_visitors")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_visitors")
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True) # Corresponds to "Last Updated"

    def __str__(self):
        return f"{self.first_name} {self.surname} (Visitor for {self.prisoner.full_name})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.surname}"

    class Meta:
        pass
    
class MedicalRecord(models.Model):
    MEDICAL_CATEGORIES = [
        ('routine', 'Routine Checkup'),
        ('emergency', 'Emergency'),
        ('chronic', 'Chronic Condition'),
        ('mental', 'Mental Health'),
        ('dental', 'Dental'),
        ('other', 'Other'),
    ]

    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE, related_name='medical_records')
    record_date = models.DateField()
    category = models.CharField(max_length=20, choices=MEDICAL_CATEGORIES)
    diagnosis = models.CharField(max_length=200)
    treatment = models.TextField()
    prescribed_medication = models.TextField(blank=True)
    next_checkup = models.DateField(blank=True, null=True)
    # Changed 'attending_staff' to 'recorded_by' and made it a ForeignKey to User
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='medical_records_recorded')
    notes = models.TextField(blank=True)
    # Removed the duplicate 'created_by' field
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_category_display()} for {self.prisoner} on {self.record_date}"



class IncidentReport(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    date_occurred = models.DateTimeField() # Includes time
    location = models.CharField(max_length=100) # Specific location within the prison
    involved_prisoners = models.ManyToManyField(Prisoner, related_name='incidents', blank=True) # Can be blank if no prisoners involved
    involved_staff = models.TextField(blank=True) # Names or IDs of staff, consider M2M to User if staff are users
    actions_taken = models.TextField()
    follow_up_required = models.BooleanField(default=False)
    follow_up_notes = models.TextField(blank=True)
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reported_incidents') # Changed from CustomUser to User
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.get_severity_display()} ({self.date_occurred.strftime('%Y-%m-%d %H:%M')})"


class PrisonerItem(models.Model):
    ITEM_TYPE_CHOICES = [
        ('money', 'Money'),
        ('clothing', 'Clothing'),
        ('personal_belonging', 'Personal Belonging'),
        ('other', 'Other'),
    ]
    CURRENCY_CHOICES = [
        ('MWK', 'Malawi Kwacha (MWK)'),
        # Add other currencies if needed in the future
    ]

    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=50, choices=ITEM_TYPE_CHOICES)
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1, blank=True, null=True,
                                           help_text="Quantity for non-monetary items. Leave blank for money.")
    initial_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, blank=True, null=True,
                                         help_text="Initial amount for money. Leave blank for other items.")
    current_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, blank=True, null=True,
                                         help_text="Current amount for money. Leave blank for other items.")
    currency = models.CharField(max_length=5, choices=CURRENCY_CHOICES, default='MWK')
    date_received = models.DateField(default=timezone.now)
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='received_prisoner_items')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_collected = models.BooleanField(default=False, help_text="Indicates if the item has been collected/reclaimed by the prisoner or their representative.") # New field

    class Meta:
        verbose_name = "Prisoner Item"
        verbose_name_plural = "Prisoner Items"
        ordering = ['-date_received', 'item_type']

    def __str__(self):
        status = " (Collected)" if self.is_collected else ""
        if self.item_type == 'money':
            return f"{self.prisoner.full_name} - Money ({self.currency} {self.current_amount}){status}"
        return f"{self.prisoner.full_name} - {self.get_item_type_display()}: {self.description} (x{self.quantity}){status}"

    def clean(self):
        if self.item_type == 'money':
            if self.quantity is not None and self.quantity != 1:
                raise ValidationError({'quantity': 'Quantity must be 1 or blank for money items.'})
            if self.initial_amount is None or self.initial_amount < 0: # Ensure initial_amount is non-negative
                raise ValidationError({'initial_amount': 'Initial amount is required and must be non-negative for money items.'})
            # Removed the current_amount initialization from here, it will be handled in save()
        else:
            if self.initial_amount is not None and self.initial_amount != 0:
                raise ValidationError({'initial_amount': 'Initial amount must be 0 or blank for non-money items.'})
            if self.current_amount is not None and self.current_amount != 0:
                raise ValidationError({'current_amount': 'Current amount must be 0 or blank for non-money items.'})
            if self.quantity is None or self.quantity < 1:
                raise ValidationError({'quantity': 'Quantity is required and must be at least 1 for non-money items.'})
        super().clean()

    def save(self, *args, **kwargs):
        is_new = self.pk is None # Check if this is a new object

        # Run full validation first
        self.full_clean()

        # For new money items, set current_amount to initial_amount
        if is_new and self.item_type == 'money':
            self.current_amount = self.initial_amount

        super().save(*args, **kwargs)


class PrisonerItemTransaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
    ]

    item = models.ForeignKey(PrisonerItem, on_delete=models.CASCADE, related_name='transactions',
                             limit_choices_to={'item_type': 'money'}) # Only allow money items
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    transaction_date = models.DateTimeField(default=timezone.now)
    transacted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='item_transactions')
    reason = models.TextField(blank=True) # Reason for withdrawal/deposit

    class Meta:
        verbose_name = "Prisoner Item Transaction"
        verbose_name_plural = "Prisoner Item Transactions"
        ordering = ['-transaction_date']

    def clean(self):
        if self.transaction_type == 'withdrawal':
            if self.amount > self.item.current_amount:
                raise ValidationError({'amount': f'Withdrawal amount ({self.amount} {self.item.currency}) exceeds current balance ({self.item.current_amount} {self.item.currency}).'})
        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean() # Call full_clean to run model-level validation
        if self.pk is None: # Only apply balance change on initial save
            if self.transaction_type == 'deposit':
                self.item.current_amount += self.amount
            elif self.transaction_type == 'withdrawal':
                self.item.current_amount -= self.amount
            self.item.save() # Save the updated current_amount on the PrisonerItem
        super().save(*args, **kwargs)


# --- NEW MODELS FOR RATION MANAGEMENT ---

class RationItem(models.Model):
    """
    Defines a type of food item managed in the prison's ration inventory.
    """
    UNIT_CHOICES = [
        ('kg', 'Kilograms (kg)'),
        ('bags', 'Bags'), # For items like flour, maize
        ('pieces', 'Pieces'), # For items like cabbage (though user said kg)
        ('liters', 'Liters (L)'), # For oil or milk
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=100, unique=True, help_text="e.g., Peas, Cabbages, Beef, Flour")
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='kg')
    current_stock_kg = models.DecimalField(
        max_digits=10, decimal_places=3, default=0.000,
        help_text="Current stock in Kilograms (kg)"
    )
    low_stock_threshold_kg = models.DecimalField(
        max_digits=10, decimal_places=3, default=50.000,
        help_text="Threshold in kg to trigger a low stock alert"
    )
    # Each prison station will manage its own inventory
    prison_station = models.ForeignKey(
        PrisonStation,
        on_delete=models.CASCADE,
        related_name='ration_items'
    )
    is_active = models.BooleanField(default=True, help_text="Whether this ration item is currently in use")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ration Item"
        verbose_name_plural = "Ration Items"
        unique_together = ('name', 'prison_station') # Ensure unique item per station
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.prison_station.name})"

    @property
    def is_low_stock(self):
        return self.current_stock_kg < self.low_stock_threshold_kg

class RationConsumption(models.Model):
    """
    Records the daily consumption of a specific ration item.
    Subtracts from the RationItem's stock.
    """
    item = models.ForeignKey(RationItem, on_delete=models.CASCADE, related_name='consumptions')
    consumption_date = models.DateField(default=timezone.now)
    quantity_used_kg = models.DecimalField(
        max_digits=10, decimal_places=3,
        help_text="Quantity consumed in Kilograms (kg)",
        validators=[MinValueValidator(0.001)] # Must be positive
    )
    # The number of prisoners fed *this item* on this day
    # This can be used for reporting/auditing against calculated needs
    num_prisoners_fed = models.PositiveIntegerField(
        help_text="Number of prisoners (including children) fed with this ration on this day"
    )
    consumed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='rations_consumed')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ration Consumption"
        verbose_name_plural = "Ration Consumptions"
        # Optionally add unique_together for item and consumption_date if only one record per item per day
        # unique_together = ('item', 'consumption_date') # Uncomment if only one consumption entry per item per day
        ordering = ['-consumption_date', 'item__name']

    def clean(self):
        # Ensure that quantity used does not exceed current stock
        if self.quantity_used_kg > self.item.current_stock_kg:
            raise ValidationError(
                {'quantity_used_kg': f"Consumption amount ({self.quantity_used_kg} kg) exceeds current stock ({self.item.current_stock_kg} kg) for {self.item.name}."}
            )

    def save(self, *args, **kwargs):
        self.full_clean() # Run custom validation before saving
        # Update the stock of the associated RationItem
        self.item.current_stock_kg -= self.quantity_used_kg
        self.item.save() # Save the updated stock
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Consumed {self.quantity_used_kg}kg of {self.item.name} on {self.consumption_date} by {self.consumed_by.username}"

class RationProcurement(models.Model):
    """
    Records the procurement (addition) of stock for a specific ration item.
    Adds to the RationItem's stock.
    """
    item = models.ForeignKey(RationItem, on_delete=models.CASCADE, related_name='procurements')
    procurement_date = models.DateField(default=timezone.now)
    quantity_procured_kg = models.DecimalField(
        max_digits=10, decimal_places=3,
        help_text="Quantity procured in Kilograms (kg)",
        validators=[MinValueValidator(0.001)] # Must be positive
    )
    procured_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='rations_procured')
    supplier = models.CharField(max_length=200, blank=True, null=True)
    invoice_number = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ration Procurement"
        verbose_name_plural = "Ration Procurements"
        ordering = ['-procurement_date', 'item__name']

    def save(self, *args, **kwargs):
        # Update the stock of the associated RationItem
        self.item.current_stock_kg += self.quantity_procured_kg
        self.item.save() # Save the updated stock
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Procured {self.quantity_procured_kg}kg of {self.item.name} on {self.procurement_date}"