# models.py
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from dateutil.relativedelta import relativedelta
from django.core.validators import MinValueValidator
from django.db.models import Count, Sum
from datetime import datetime 
import math
from django.conf import settings
from django.core.exceptions import ValidationError
import base64
import hashlib
import json

User = get_user_model()

# Import Region and PrisonStation from accounts app to avoid duplication
from accounts.models import Region, PrisonStation

class Prisoner(models.Model):
    PRISONER_CLASS_CHOICES = [
        ('convicted', 'Convicted'),
        ('remand', 'Remand'),
    ]

    SEX_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
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
    document = models.FileField(upload_to='prisoner_documents/', blank=True, null=True,
        help_text="Attach PDF document (court orders, medical reports, etc.)")
    date_admitted = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    date_released = models.DateField(blank=True, null=True) 
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_prisoners')
    last_modified = models.DateTimeField(auto_now=True)

    # ============ BIOMETRIC / FINGERPRINT FIELDS ============
    fingerprint_template = models.TextField(blank=True, null=True, 
        help_text="Base64 encoded fingerprint template")
    fingerprint_hash = models.CharField(max_length=64, blank=True, null=True,
        help_text="SHA-256 hash of fingerprint for quick matching")
    fingerprint_captured_at = models.DateTimeField(blank=True, null=True)
    fingerprint_captured_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='captured_fingerprints'
    )
    fingerprint_quality = models.IntegerField(blank=True, null=True, 
        help_text="Quality score 0-100")
    fingerprint_device = models.ForeignKey(
        'FingerprintDevice',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='captured_fingerprints'
    )
    
    # Identity tracking
    previous_identities = models.ManyToManyField(
        'self', 
        symmetrical=False, 
        blank=True, 
        related_name='linked_identities'
    )
    is_identity_verified = models.BooleanField(default=False,
        help_text="Indicates if identity has been verified via fingerprint")
    identity_verified_at = models.DateTimeField(blank=True, null=True)
    identity_verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_identities'
    )
    identity_verification_notes = models.TextField(blank=True,
        help_text="Notes about identity verification process")

    # ============ RECIDIVISM TRACKING ============
    is_recidivist = models.BooleanField(default=False,
        help_text="Indicates if this prisoner has been incarcerated before")
    previous_prisoner_numbers = models.TextField(blank=True,
        help_text="Comma-separated list of previous prisoner numbers")
    first_incarceration_date = models.DateField(blank=True, null=True,
        help_text="Date of first incarceration (if recidivist)")
    recidivism_detected_at = models.DateTimeField(blank=True, null=True,
        help_text="When recidivism was detected")
    recidivism_detected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='detected_recidivists'
    )
    recidivism_notes = models.TextField(blank=True,
        help_text="Notes about recidivism detection")

    def __str__(self):
        return f"{self.prisoner_number} - {self.first_name} {self.surname}"

    @property
    def has_fingerprint(self):
        return bool(self.fingerprint_template and self.fingerprint_hash)

    @property
    def full_name(self):
        return f"{self.first_name} {self.middle_name} {self.surname}".strip()

    @property
    def is_biometrically_verified(self):
        return self.is_identity_verified and self.has_fingerprint

    def get_fingerprint_metadata(self):
        """Get fingerprint metadata as dictionary"""
        if not self.has_fingerprint:
            return None
        return {
            'has_fingerprint': True,
            'quality': self.fingerprint_quality,
            'captured_at': self.fingerprint_captured_at.isoformat() if self.fingerprint_captured_at else None,
            'captured_by': self.fingerprint_captured_by.username if self.fingerprint_captured_by else None,
            'device': self.fingerprint_device.name if self.fingerprint_device else None,
            'is_verified': self.is_identity_verified
        }

    def save(self, *args, **kwargs):
        # Generate fingerprint hash from template if not set
        if self.fingerprint_template and not self.fingerprint_hash:
            self.fingerprint_hash = hashlib.sha256(
                self.fingerprint_template.encode()
            ).hexdigest()
        super().save(*args, **kwargs)


class PrisonerReleaseReview(models.Model):
    REVIEW_ROLE_CHOICES = [
        ('officer_in_charge', 'Officer in Charge'),
        ('station_officer', 'Station Officer'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE, related_name='release_reviews')
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requested_release_reviews'
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_release_reviews'
    )
    review_role = models.CharField(max_length=25, choices=REVIEW_ROLE_CHOICES)
    station = models.ForeignKey(PrisonStation, on_delete=models.CASCADE, related_name='release_reviews')
    release_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.prisoner.prisoner_number} - {self.get_review_role_display()}"


class ConvictedPrisoner(models.Model):
    OFFENSE_CHOICES = sorted([
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
    notes = models.CharField(blank=True)
    reduction_months = models.FloatField(default=0, blank=True, validators=[MinValueValidator(0)])
    reduction_notes = models.CharField(blank=True)

    def save(self, *args, **kwargs):
        AVG_DAYS_PER_MONTH = 30.4375
        if self.wef_date and self.sentence:
            adjusted_wef = self.wef_date - relativedelta(days=1)
            sentence_months_val = int(self.sentence)
            sentence_fraction = self.sentence - sentence_months_val
            sentence_days = int(sentence_fraction * AVG_DAYS_PER_MONTH)
            self.date_of_release = adjusted_wef + relativedelta(months=sentence_months_val, days=sentence_days)

        if self.date_of_release:
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
    OFFENSE_CHOICES = ConvictedPrisoner.OFFENSE_CHOICES

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
    ]

    RELIGION_CHOICES = [
        ('christian', 'Christian'),
        ('muslim', 'Muslim'),
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
    ]

    HEALTH_CHOICES = [
        ('none', 'None'),
        ('tb', 'TB'),
        ('hiv', 'HIV'),
        ('malaria', 'Malaria prone'),
        ('ptsd', 'PTSD'),
        ('stis', 'STIs'),
        ('malnutrition', 'Malnutrition'),
    ]

    prisoner = models.OneToOneField(Prisoner, on_delete=models.CASCADE, primary_key=True, related_name='physical')
    height = models.DecimalField(max_digits=5, decimal_places=2, help_text="Height in cm")
    weight = models.DecimalField(max_digits=5, decimal_places=2, help_text="Weight in kg")
    body_build = models.CharField(max_length=20, choices=BODY_BUILD_CHOICES)
    skin_color = models.CharField(max_length=20, choices=SKIN_COLOR_CHOICES)
    eyes_color = models.CharField(max_length=20, choices=EYES_COLOR_CHOICES)
    head_abnormalities = models.CharField(max_length=100, blank=True)
    health_status = models.CharField(max_length=20, choices=HEALTH_CHOICES, default='none')
    circumcised = models.BooleanField(default=False)
    marks_tattoos_scars = models.CharField(blank=True, max_length=255)
    has_child = models.BooleanField(default=False)
    children_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Physical Characteristics for {self.prisoner.prisoner_number}"

class RehabilitationProgram(models.Model):
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('expert', 'Expert'),
        ('not_applicable', 'Not Applicable'),
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
        ('approve', 'Approve'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('add_item', 'Add Item'),
        ('withdraw_money', 'Withdraw Money'),
        ('collect_item', 'Collect Item'),
        ('capture_fingerprint', 'Capture Fingerprint'),
        ('verify_identity', 'Verify Identity'),
        ('fingerprint_match', 'Fingerprint Match'),
        ('link_identity', 'Link Identity'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    model = models.CharField(max_length=50)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    details = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user} {self.action}d {self.model} {self.object_id or ''} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

class ReleaseOnRemission(models.Model):
    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE)
    release_date = models.DateField()
    original_sentence = models.FloatField()
    remission_months = models.DecimalField(max_digits=5, decimal_places=2)
    reduction_months = models.FloatField(default=0)
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
    ]

    ID_TYPE_CHOICES = [
        ('national_id', 'National ID'),
        ('passport', 'Passport'),
        ('drivers_license', 'Driver\'s License'),
    ]

    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=50)
    surname = models.CharField(max_length=50)
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    id_number = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    purpose_of_visit = models.TextField(blank=True, null=True)
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
    last_updated = models.DateTimeField(auto_now=True)

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
    ]

    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE, related_name='medical_records')
    record_date = models.DateField()
    category = models.CharField(max_length=20, choices=MEDICAL_CATEGORIES)
    diagnosis = models.CharField(max_length=200)
    treatment = models.TextField()
    prescribed_medication = models.TextField(blank=True)
    next_checkup = models.DateField(blank=True, null=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='medical_records_recorded')
    notes = models.TextField(blank=True)
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
    date_occurred = models.DateTimeField()
    location = models.CharField(max_length=100)
    involved_prisoners = models.ManyToManyField(Prisoner, related_name='incidents', blank=True)
    involved_staff = models.TextField(blank=True)
    actions_taken = models.TextField()
    follow_up_required = models.BooleanField(default=False)
    follow_up_notes = models.TextField(blank=True)
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reported_incidents')
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
    is_collected = models.BooleanField(default=False, help_text="Indicates if the item has been collected/reclaimed by the prisoner or their representative.")

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
            if self.initial_amount is None or self.initial_amount < 0:
                raise ValidationError({'initial_amount': 'Initial amount is required and must be non-negative for money items.'})
        else:
            if self.initial_amount is not None and self.initial_amount != 0:
                raise ValidationError({'initial_amount': 'Initial amount must be 0 or blank for non-money items.'})
            if self.current_amount is not None and self.current_amount != 0:
                raise ValidationError({'current_amount': 'Current amount must be 0 or blank for non-money items.'})
            if self.quantity is None or self.quantity < 1:
                raise ValidationError({'quantity': 'Quantity is required and must be at least 1 for non-money items.'})
        super().clean()

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        self.full_clean()
        if is_new and self.item_type == 'money':
            self.current_amount = self.initial_amount
        super().save(*args, **kwargs)

class PrisonerItemTransaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
    ]

    item = models.ForeignKey(PrisonerItem, on_delete=models.CASCADE, related_name='transactions',
                             limit_choices_to={'item_type': 'money'})
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    transaction_date = models.DateTimeField(default=timezone.now)
    transacted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='item_transactions')
    reason = models.TextField(blank=True)

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
        self.full_clean()
        if self.pk is None:
            if self.transaction_type == 'deposit':
                self.item.current_amount += self.amount
            elif self.transaction_type == 'withdrawal':
                self.item.current_amount -= self.amount
            self.item.save()
        super().save(*args, **kwargs)

# ============ BIOMETRIC / FINGERPRINT MODELS ============

class FingerprintDevice(models.Model):
    """Manage fingerprint scanner devices"""
    DEVICE_STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Maintenance'),
        ('offline', 'Offline'),
    ]
    
    DEVICE_TYPE_CHOICES = [
        ('integrated', 'Integrated (Laptop)'),
        ('usb', 'USB Scanner'),
        ('mobile', 'Mobile Scanner'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=100)
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPE_CHOICES, default='integrated')
    serial_number = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=DEVICE_STATUS_CHOICES, default='active')
    prison_station = models.ForeignKey(
        PrisonStation, 
        on_delete=models.CASCADE, 
        related_name='fingerprint_devices'
    )
    last_used_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Fingerprint Device"
        verbose_name_plural = "Fingerprint Devices"
        ordering = ['prison_station', 'name']
        
    def __str__(self):
        return f"{self.name} ({self.get_device_type_display()}) - {self.status}"


class FingerprintMatch(models.Model):
    """Track fingerprint matching history for auditing"""
    MATCH_STATUS_CHOICES = [
        ('exact', 'Exact Match'),
        ('probable', 'Probable Match'),
        ('potential', 'Potential Match'),
        ('no_match', 'No Match'),
        ('error', 'Match Error'),
    ]
    
    searched_prisoner = models.ForeignKey(
        Prisoner, 
        on_delete=models.CASCADE, 
        related_name='searched_fingerprints',
        null=True,
        blank=True,
        help_text="The prisoner whose fingerprint was used for search (null for unknown)"
    )
    matched_prisoner = models.ForeignKey(
        Prisoner, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='matched_fingerprints'
    )
    match_score = models.FloatField(help_text="Match confidence score 0-100")
    match_status = models.CharField(max_length=20, choices=MATCH_STATUS_CHOICES)
    search_timestamp = models.DateTimeField(auto_now_add=True)
    searched_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    search_ip = models.GenericIPAddressField(blank=True, null=True)
    match_details = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Fingerprint Match"
        verbose_name_plural = "Fingerprint Matches"
        ordering = ['-search_timestamp']
        indexes = [
            models.Index(fields=['searched_prisoner', '-search_timestamp']),
            models.Index(fields=['matched_prisoner', '-search_timestamp']),
            models.Index(fields=['match_status']),
        ]

    def __str__(self):
        status = "Matched" if self.matched_prisoner else "No Match"
        return f"{self.searched_prisoner or 'Unknown'} - {status} ({self.match_score:.1f}%)"


class FingerprintAuditLog(models.Model):
    """Detailed audit log for fingerprint operations"""
    OPERATION_CHOICES = [
        ('capture', 'Fingerprint Capture'),
        ('verify', 'Identity Verification'),
        ('search', 'Fingerprint Search'),
        ('match', 'Fingerprint Match'),
        ('link', 'Identity Link'),
        ('unlink', 'Identity Unlink'),
        ('delete', 'Fingerprint Delete'),
        ('update', 'Fingerprint Update'),
    ]
    
    prisoner = models.ForeignKey(
        Prisoner, 
        on_delete=models.CASCADE, 
        related_name='fingerprint_audits'
    )
    operation = models.CharField(max_length=20, choices=OPERATION_CHOICES)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    performed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)  # Make this nullable
    details = models.JSONField(default=dict, blank=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Fingerprint Audit Log"
        verbose_name_plural = "Fingerprint Audit Logs"
        ordering = ['-performed_at']
        indexes = [
            models.Index(fields=['prisoner', '-performed_at']),
            models.Index(fields=['operation', '-performed_at']),
        ]


class InmateReturn(models.Model):
    """
    Comprehensive model for inmate returns and reports.
    Manages all types of prison returns including convicted, remanded, 
    foreigner, medical, and special category returns.
    """
    
    # ============ RETURN TYPE CHOICES ============
    RETURN_TYPE_CHOICES = [
        ('convicted', 'Convicted Inmates Return'),
        ('remanded', 'Remanded Inmates Return'),
        ('remand_murder', 'Remanded Murder Cases Return'),
        ('convicted_foreigners', 'Convicted Foreigners Return'),
        ('foreigners_remand', 'Foreigners Remand Return'),
        ('general_remandees', 'General Remandees Return'),
        ('chronically_ill', 'Chronically Ill Inmates Return'),
        ('convicted_elderly', 'Convicted Elderly (70 yrs & above)'),
        ('convicted_pregnant', 'Convicted Pregnant Inmates'),
        ('discharged_after_reductions', 'Discharged After Effecting Months Reduction'),
        ('children_with_mothers', 'Children Accompanying Their Mothers'),
        ('convicted_pregnant_mothers', 'Convicted Pregnant Mothers'),
        ('remand_pregnant_mothers_murder', 'Remandees Pregnant Mothers on Homicide'),
        ('children_with_mothers_homicide', 'Children Accompanying Mothers on Homicide'),
        ('pending_cases', 'Pending Cases Return'),
        ('due_discharge', 'Due Discharge'),
        ('lockup_summary', 'Lockup Summary'),
        ('quarterly', 'Quarterly Report'),
        ('annual', 'Annual Report'),
        ('monthly_statistics', 'Monthly Statistics'),
        ('weekly_summary', 'Weekly Summary'),
        ('special', 'Special Return'),
        ('other', 'Other Return'),
    ]
    
    # ============ STATUS CHOICES ============
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted for Approval'),
        ('processing', 'Processing'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]
    
    # ============ BASIC INFORMATION ============
    title = models.CharField(
        max_length=300, 
        help_text="Descriptive title for the return (e.g., 'Convicted Inmates Return - Zomba - November 2026')"
    )
    return_type = models.CharField(
        max_length=50, 
        choices=RETURN_TYPE_CHOICES,
        help_text="Type of return being generated"
    )
    description = models.TextField(
        blank=True, 
        help_text="Optional detailed description of the return"
    )
    
    # ============ PERIOD INFORMATION ============
    month = models.IntegerField(
        blank=True, 
        null=True,
        help_text="Month (1-12) for period-specific returns"
    )
    year = models.IntegerField(
        blank=True, 
        null=True,
        help_text="Year for period-specific returns"
    )
    start_date = models.DateField(
        blank=True, 
        null=True,
        help_text="Start date for custom date ranges"
    )
    end_date = models.DateField(
        blank=True, 
        null=True,
        help_text="End date for custom date ranges"
    )
    reporting_period = models.CharField(
        max_length=100,
        blank=True,
        help_text="Description of reporting period (e.g., 'Q1 2026', 'January 2026')"
    )
    
    # ============ STATION INFORMATION ============
    station = models.ForeignKey(
        PrisonStation,
        on_delete=models.CASCADE,
        related_name='inmate_returns',
        help_text="Prison station that this return belongs to"
    )
    region = models.ForeignKey(
        Region,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inmate_returns',
        help_text="Region of the station (auto-populated)"
    )
    
    # ============ FILE MANAGEMENT ============
    file = models.FileField(
        upload_to='inmate_returns/%Y/%m/',
        blank=True,
        null=True,
        help_text="Uploaded file (PDF, Word, Excel, CSV, etc.)"
    )
    file_name = models.CharField(
        max_length=255, 
        blank=True,
        help_text="Original file name"
    )
    file_size = models.BigIntegerField(
        blank=True, 
        null=True, 
        help_text="File size in bytes"
    )
    file_type = models.CharField(
        max_length=50, 
        blank=True,
        help_text="File extension/type"
    )
    file_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 hash of the file for integrity checking"
    )
    file_uploaded_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the file was uploaded"
    )
    
    # ============ CSV DATA MANAGEMENT ============
    has_csv_data = models.BooleanField(
        default=False,
        help_text="Whether this return has imported CSV data"
    )
    csv_row_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of rows imported from CSV"
    )
    csv_imported_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When CSV data was imported"
    )
    csv_imported_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='imported_csv_returns',
        help_text="User who imported the CSV data"
    )
    
    # ============ WORKFLOW STATUS ============
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='draft'
    )
    status_history = models.JSONField(
        default=list,
        blank=True,
        help_text="History of status changes with timestamps and users"
    )
    
    # ============ APPROVAL TRACKING ============
    submitted_at = models.DateTimeField(
        blank=True, 
        null=True,
        help_text="When the return was submitted for approval"
    )
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_returns',
        help_text="User who submitted the return"
    )
    approved_at = models.DateTimeField(
        blank=True, 
        null=True,
        help_text="When the return was approved"
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_returns',
        help_text="User who approved the return"
    )
    approval_notes = models.TextField(
        blank=True,
        help_text="Notes from the approver"
    )
    rejected_at = models.DateTimeField(
        blank=True, 
        null=True,
        help_text="When the return was rejected"
    )
    rejected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rejected_returns',
        help_text="User who rejected the return"
    )
    rejection_reason = models.TextField(
        blank=True,
        help_text="Reason for rejection"
    )
    completed_at = models.DateTimeField(
        blank=True, 
        null=True,
        help_text="When the return was marked as completed"
    )
    completed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_returns',
        help_text="User who marked the return as completed"
    )
    
    # ============ REVIEWER ASSIGNMENT ============
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_returns',
        help_text="User assigned to review this return"
    )
    review_deadline = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Deadline for review/approval"
    )
    
    # ============ METADATA AND STATISTICS ============
    total_records = models.PositiveIntegerField(
        default=0,
        help_text="Total number of records in this return"
    )
    unique_prisoners = models.PositiveIntegerField(
        default=0,
        help_text="Number of unique prisoners in the return"
    )
    male_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of male prisoners"
    )
    female_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of female prisoners"
    )
    offense_breakdown = models.JSONField(
        default=dict,
        blank=True,
        help_text="Breakdown of offenses with counts"
    )
    age_distribution = models.JSONField(
        default=dict,
        blank=True,
        help_text="Age distribution statistics"
    )
    summary_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Comprehensive summary data for the return"
    )
    
    # ============ NOTES AND REMARKS ============
    remarks = models.TextField(
        blank=True,
        help_text="General remarks or notes about this return"
    )
    internal_notes = models.TextField(
        blank=True,
        help_text="Internal notes for staff (not shown to external users)"
    )
    
    # ============ VISIBILITY AND PERMISSIONS ============
    is_public = models.BooleanField(
        default=False,
        help_text="Whether this return is publicly visible"
    )
    is_template = models.BooleanField(
        default=False,
        help_text="Whether this return can be used as a template"
    )
    
    # ============ AUDIT TRAIL ============
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_returns',
        help_text="User who created this return"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this return was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this return was last updated"
    )
    last_accessed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When this return was last accessed"
    )
    
    # ============ METADATA ============
    version = models.PositiveIntegerField(
        default=1,
        help_text="Version number of this return"
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Tags for categorization and search"
    )
    custom_fields = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom fields for additional data"
    )
    
    # ============ META OPTIONS ============
    class Meta:
        verbose_name = "Inmate Return"
        verbose_name_plural = "Inmate Returns"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['station', '-created_at']),
            models.Index(fields=['return_type', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['month', 'year']),
            models.Index(fields=['submitted_at']),
            models.Index(fields=['approved_at']),
            models.Index(fields=['created_by']),
            models.Index(fields=['assigned_to']),
        ]
        unique_together = [
            ['station', 'return_type', 'month', 'year'],
        ]
        
    # ============ STRING REPRESENTATION ============
    def __str__(self):
        if self.month and self.year:
            month_name = self.get_month_display()
            return f"{self.title} - {self.station.name} - {month_name} {self.year}"
        return f"{self.title} - {self.station.name} ({self.created_at.strftime('%Y-%m-%d')})"
    
    # ============ DISPLAY HELPERS ============
    def get_month_display(self):
        """Return month name"""
        if self.month:
            months = ['January', 'February', 'March', 'April', 'May', 'June',
                     'July', 'August', 'September', 'October', 'November', 'December']
            return months[self.month - 1]
        return None
    
    def get_status_display(self):
        """Return human-readable status"""
        return dict(self.STATUS_CHOICES).get(self.status, self.status)
    
    def get_return_type_display(self):
        """Return human-readable return type"""
        return dict(self.RETURN_TYPE_CHOICES).get(self.return_type, self.return_type)
    
    def get_file_size_display(self):
        """Return human-readable file size"""
        if self.file_size:
            size = self.file_size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        return "Unknown"
    
    def get_reporting_period_display(self):
        """Get human-readable reporting period"""
        if self.reporting_period:
            return self.reporting_period
        if self.month and self.year:
            return f"{self.get_month_display()} {self.year}"
        if self.start_date and self.end_date:
            return f"{self.start_date.strftime('%d-%m-%Y')} to {self.end_date.strftime('%d-%m-%Y')}"
        return "N/A"
    
    # ============ WORKFLOW METHODS ============
    def can_edit(self, user):
        """Check if user can edit this return"""
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or (hasattr(user, 'is_super_admin') and user.is_super_admin()):
            return True
        if self.status not in ['draft', 'rejected']:
            return False
        if self.created_by == user:
            return True
        if hasattr(user, 'prison_station') and user.prison_station == self.station:
            return True
        return False
    
    def can_delete(self, user):
        """Check if user can delete this return"""
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or (hasattr(user, 'is_super_admin') and user.is_super_admin()):
            return True
        if self.status not in ['draft', 'rejected']:
            return False
        if self.created_by == user:
            return True
        if (hasattr(user, 'is_prison_admin') and user.is_prison_admin() and 
            hasattr(user, 'prison_station') and user.prison_station == self.station):
            return True
        return False
    
    def can_approve(self, user):
        """Check if user can approve this return"""
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or (hasattr(user, 'is_super_admin') and user.is_super_admin()):
            return True
        if hasattr(user, 'is_officer_in_charge') and user.is_officer_in_charge():
            if hasattr(user, 'prison_station') and user.prison_station == self.station:
                return True
        if hasattr(user, 'is_station_officer') and user.is_station_officer():
            if hasattr(user, 'prison_station') and user.prison_station == self.station:
                return True
        return False
    
    # ============ STATUS TRANSITIONS ============
    def submit(self, user):
        """Submit return for approval"""
        if self.status != 'draft':
            raise ValidationError(f"Cannot submit return with status '{self.get_status_display()}'")
        
        if not self.data_rows.exists() and not self.file:
            raise ValidationError("Cannot submit a return with no data. Please add data or upload a file.")
        
        self.status = 'submitted'
        self.submitted_at = timezone.now()
        self.submitted_by = user
        self._add_status_history('submitted', user, 'Return submitted for approval')
        self.save()
    
    def process(self, user):
        """Start processing the return"""
        if self.status != 'submitted':
            raise ValidationError(f"Cannot process return with status '{self.get_status_display()}'")
        
        self.status = 'processing'
        self._add_status_history('processing', user, 'Return being processed')
        self.save()
    
    def review(self, user):
        """Mark return as under review"""
        if self.status not in ['submitted', 'processing']:
            raise ValidationError(f"Cannot review return with status '{self.get_status_display()}'")
        
        self.status = 'under_review'
        self.assigned_to = user
        self._add_status_history('under_review', user, 'Return under review')
        self.save()
    
    def approve(self, user, notes=''):
        """Approve the return"""
        if self.status not in ['submitted', 'processing', 'under_review']:
            raise ValidationError(f"Cannot approve return with status '{self.get_status_display()}'")
        
        self.status = 'approved'
        self.approved_at = timezone.now()
        self.approved_by = user
        self.approval_notes = notes
        self._add_status_history('approved', user, f'Return approved. Notes: {notes}')
        self.save()
    
    def reject(self, user, reason):
        """Reject the return"""
        if self.status not in ['submitted', 'processing', 'under_review']:
            raise ValidationError(f"Cannot reject return with status '{self.get_status_display()}'")
        
        if not reason:
            raise ValidationError("Rejection reason is required")
        
        self.status = 'rejected'
        self.rejected_at = timezone.now()
        self.rejected_by = user
        self.rejection_reason = reason
        self._add_status_history('rejected', user, f'Return rejected. Reason: {reason}')
        self.save()
    
    def complete(self):
        """Mark return as completed"""
        if self.status != 'approved':
            raise ValidationError(f"Cannot complete return with status '{self.get_status_display()}'")
        
        self.status = 'completed'
        self.completed_at = timezone.now()
        self._add_status_history('completed', None, 'Return completed')
        self.save()
    
    def archive(self, user):
        """Archive the return"""
        if self.status not in ['approved', 'completed']:
            raise ValidationError(f"Cannot archive return with status '{self.get_status_display()}'")
        
        self.status = 'archived'
        self._add_status_history('archived', user, 'Return archived')
        self.save()
    
    def _add_status_history(self, status, user, note=''):
        """Add entry to status history"""
        entry = {
            'status': status,
            'timestamp': timezone.now().isoformat(),
            'user': user.username if user else 'System',
            'user_id': user.id if user else None,
            'note': note
        }
        self.status_history.append(entry)
        if len(self.status_history) > 50:  # Limit history size
            self.status_history = self.status_history[-50:]
    
    # ============ DATA MANAGEMENT ============
    def update_summary(self):
        """Update summary statistics"""
        data_rows = self.data_rows.all()
        
        self.total_records = data_rows.count()
        self.unique_prisoners = data_rows.values('prisoner_number').distinct().count()
        self.male_count = data_rows.filter(sex__iexact='M').count()
        self.female_count = data_rows.filter(sex__iexact='F').count()
        
        # Offense breakdown
        offense_data = {}
        for row in data_rows.values('offense').exclude(offense__isnull=True).exclude(offense=''):
            offense = row.get('offense')
            if offense:
                offense_data[offense] = offense_data.get(offense, 0) + 1
        self.offense_breakdown = offense_data
        
        # Age distribution
        age_groups = {
            '0-18': 0,
            '19-30': 0,
            '31-45': 0,
            '46-60': 0,
            '61+': 0,
            'Unknown': 0
        }
        for row in data_rows:
            if row.age:
                if row.age <= 18:
                    age_groups['0-18'] += 1
                elif row.age <= 30:
                    age_groups['19-30'] += 1
                elif row.age <= 45:
                    age_groups['31-45'] += 1
                elif row.age <= 60:
                    age_groups['46-60'] += 1
                else:
                    age_groups['61+'] += 1
            else:
                age_groups['Unknown'] += 1
        self.age_distribution = age_groups
        
        # Summary data
        self.summary_data = {
            'total_records': self.total_records,
            'unique_prisoners': self.unique_prisoners,
            'male_count': self.male_count,
            'female_count': self.female_count,
            'offense_breakdown': self.offense_breakdown,
            'age_distribution': self.age_distribution,
            'updated_at': timezone.now().isoformat(),
        }
        
        self.save(update_fields=[
            'total_records', 'unique_prisoners', 'male_count', 'female_count',
            'offense_breakdown', 'age_distribution', 'summary_data'
        ])
    
    def get_summary(self):
        """Get summary data"""
        if not self.summary_data:
            self.update_summary()
        return self.summary_data
    
    def get_data_by_offense(self, limit=10):
        """Get top offenses by count"""
        if self.offense_breakdown:
            sorted_offenses = sorted(
                self.offense_breakdown.items(),
                key=lambda x: x[1],
                reverse=True
            )
            return sorted_offenses[:limit]
        return []
    
    def get_data_by_gender(self):
        """Get gender breakdown"""
        return {
            'male': self.male_count,
            'female': self.female_count,
            'unknown': self.total_records - self.male_count - self.female_count
        }
    
    def get_data_by_age_group(self):
        """Get age distribution"""
        return self.age_distribution
    
    # ============ VALIDATION ============
    def clean(self):
        """Validate the model"""
        if self.month and (self.month < 1 or self.month > 12):
            raise ValidationError({'month': 'Month must be between 1 and 12'})
        
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({'start_date': 'Start date must be before end date'})
    
    # ============ SAVE OVERRIDE ============
    def save(self, *args, **kwargs):
        """Save with additional processing"""
        # Auto-populate region from station
        if self.station and self.station.region:
            self.region = self.station.region
        
        # Set reporting period if not set
        if not self.reporting_period:
            if self.month and self.year:
                self.reporting_period = f"{self.get_month_display()} {self.year}"
            elif self.start_date and self.end_date:
                self.reporting_period = f"{self.start_date.strftime('%d-%m-%Y')} to {self.end_date.strftime('%d-%m-%Y')}"
        
        # Auto-generate title if not set
        if not self.title:
            type_label = dict(self.RETURN_TYPE_CHOICES).get(self.return_type, self.return_type)
            if self.month and self.year:
                month_name = self.get_month_display()
                self.title = f"{type_label} - {self.station.name} - {month_name} {self.year}"
            else:
                self.title = f"{type_label} - {self.station.name} - {timezone.now().strftime('%Y-%m-%d')}"
        
        super().save(*args, **kwargs)
    
    # ============ EXPORT METHODS ============
    def export_to_csv(self):
        """Export return data to CSV"""
        import csv
        import io
        
        output = io.StringIO()
        
        # Get columns from template or auto-detect
        columns = self._get_columns()
        
        # Write headers
        writer = csv.writer(output)
        writer.writerow([col['header'] for col in columns])
        
        # Write data
        for row in self.data_rows.all().order_by('row_number'):
            row_data = []
            for col in columns:
                value = getattr(row, col['key'], '')
                if isinstance(value, date):
                    value = value.strftime('%d-%m-%Y')
                elif value is None:
                    value = ''
                row_data.append(value)
            writer.writerow(row_data)
        
        return output.getvalue()
    
    def _get_columns(self):
        """Get columns for export"""
        # Try to get from template
        try:
            from .models import ReturnTemplate
            template = ReturnTemplate.objects.get(return_type=self.return_type)
            return template.columns
        except:
            pass
        
        # Auto-detect from data
        if self.data_rows.exists():
            first_row = self.data_rows.first()
            columns = []
            for field in InmateReturnData._meta.fields:
                field_name = field.name
                if field_name not in ['id', 'inmate_return', 'additional_data', 'created_at', 'updated_at']:
                    value = getattr(first_row, field_name)
                    if value:
                        columns.append({
                            'key': field_name,
                            'header': field_name.replace('_', ' ').title()
                        })
            return columns
        
        # Default columns
        return [
            {'key': 'serial_no', 'header': 'Ser. No.'},
            {'key': 'prisoner_number', 'header': 'Prisoner No.'},
            {'key': 'full_name', 'header': 'Full Name'},
            {'key': 'sex', 'header': 'Sex'},
            {'key': 'age', 'header': 'Age'},
            {'key': 'offense', 'header': 'Offense'},
            {'key': 'remarks', 'header': 'Remarks'},
        ]
    
    def get_data_dict(self):
        """Get all data as a dictionary"""
        data = {
            'id': self.id,
            'title': self.title,
            'return_type': self.return_type,
            'return_type_label': self.get_return_type_display(),
            'status': self.status,
            'status_label': self.get_status_display(),
            'station': self.station.name if self.station else None,
            'station_id': self.station.id if self.station else None,
            'region': self.region.name if self.region else None,
            'month': self.month,
            'month_name': self.get_month_display(),
            'year': self.year,
            'reporting_period': self.get_reporting_period_display(),
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'total_records': self.total_records,
            'unique_prisoners': self.unique_prisoners,
            'male_count': self.male_count,
            'female_count': self.female_count,
            'has_csv_data': self.has_csv_data,
            'csv_row_count': self.csv_row_count,
            'file_name': self.file_name,
            'file_size': self.file_size,
            'file_type': self.file_type,
            'created_by': self.created_by.username if self.created_by else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'remarks': self.remarks,
            'approval_notes': self.approval_notes,
            'rejection_reason': self.rejection_reason,
            'status_history': self.status_history,
            'summary': self.summary_data,
            'offense_breakdown': self.offense_breakdown,
            'age_distribution': self.age_distribution,
            'tags': self.tags,
            'custom_fields': self.custom_fields,
        }
        return data
    
    def get_status_history_display(self):
        """Get formatted status history for display"""
        history = []
        for entry in self.status_history:
            history.append({
                'status': entry.get('status', ''),
                'status_label': dict(self.STATUS_CHOICES).get(entry.get('status', ''), entry.get('status', '')),
                'timestamp': entry.get('timestamp', ''),
                'user': entry.get('user', 'System'),
                'note': entry.get('note', '')
            })
        return history


class InmateReturnData(models.Model):
    """
    Data rows for inmate returns. Each row represents a prisoner record.
    Comprehensive fields to support all return types.
    """
    
    # ============ RELATIONSHIPS ============
    inmate_return = models.ForeignKey(
        InmateReturn,
        on_delete=models.CASCADE,
        related_name='data_rows',
        help_text="The return this data belongs to"
    )
    
    # ============ ROW IDENTIFICATION ============
    row_number = models.PositiveIntegerField(
        help_text="Row number in the CSV/return"
    )
    serial_no = models.PositiveIntegerField(
        blank=True, 
        null=True,
        help_text="Serial number within the return"
    )
    
    # ============ PRISONER IDENTIFICATION ============
    prisoner_number = models.CharField(
        max_length=20, 
        blank=True,
        help_text="Prisoner number"
    )
    full_name = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Full name of the prisoner"
    )
    first_name = models.CharField(
        max_length=100, 
        blank=True,
        help_text="First name"
    )
    surname = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Surname"
    )
    middle_name = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Middle name"
    )
    
    # ============ DEMOGRAPHICS ============
    sex = models.CharField(
        max_length=10, 
        blank=True,
        choices=[('M', 'Male'), ('F', 'Female'), ('U', 'Unknown')],
        help_text="Gender"
    )
    age = models.PositiveIntegerField(
        blank=True, 
        null=True,
        help_text="Age in years"
    )
    date_of_birth = models.DateField(
        blank=True, 
        null=True,
        help_text="Date of birth"
    )
    
    # ============ PRISONER CLASSIFICATION ============
    prisoner_class = models.CharField(
        max_length=20, 
        blank=True,
        choices=[('convicted', 'Convicted'), ('remand', 'Remand'), ('pending', 'Pending')],
        help_text="Prisoner class"
    )
    is_convicted = models.BooleanField(
        default=False,
        help_text="Whether the prisoner is convicted"
    )
    is_remand = models.BooleanField(
        default=False,
        help_text="Whether the prisoner is on remand"
    )
    
    # ============ OFFENSE AND COURT ============
    offense = models.CharField(
        max_length=300, 
        blank=True,
        help_text="Offense committed"
    )
    offense_code = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Offense code or section"
    )
    court = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Court name"
    )
    court_case_number = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Court case number"
    )
    judge_name = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Judge/Magistrate name"
    )
    case_status = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Case status (e.g., pending, concluded)"
    )
    
    # ============ SENTENCE DETAILS ============
    sentence_months = models.FloatField(
        blank=True, 
        null=True,
        help_text="Sentence length in months"
    )
    sentence_years = models.FloatField(
        blank=True, 
        null=True,
        help_text="Sentence length in years"
    )
    sentence_days = models.PositiveIntegerField(
        blank=True, 
        null=True,
        help_text="Additional sentence days"
    )
    sentence_type = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('imprisonment', 'Imprisonment'),
            ('fine', 'Fine'),
            ('community_service', 'Community Service'),
            ('suspended', 'Suspended Sentence'),
            ('life', 'Life Imprisonment'),
            ('death', 'Death Sentence'),
        ],
        help_text="Type of sentence"
    )
    
    # ============ DATE FIELDS ============
    date_of_committal = models.DateField(
        blank=True, 
        null=True,
        help_text="Date of committal"
    )
    date_of_admission = models.DateField(
        blank=True, 
        null=True,
        help_text="Date of admission to prison"
    )
    date_of_conviction = models.DateField(
        blank=True, 
        null=True,
        help_text="Date of conviction"
    )
    date_of_sentence = models.DateField(
        blank=True, 
        null=True,
        help_text="Date of sentencing"
    )
    release_date_without_remission = models.DateField(
        blank=True, 
        null=True,
        help_text="Release date without remission"
    )
    release_date_with_remission = models.DateField(
        blank=True, 
        null=True,
        help_text="Release date with remission"
    )
    expected_date_release = models.DateField(
        blank=True, 
        null=True,
        help_text="Expected date of release"
    )
    actual_release_date = models.DateField(
        blank=True, 
        null=True,
        help_text="Actual date of release"
    )
    last_court_appearance = models.DateField(
        blank=True, 
        null=True,
        help_text="Last court appearance date"
    )
    next_court_date = models.DateField(
        blank=True, 
        null=True,
        help_text="Next court date"
    )
    
    # ============ REMISSION AND REDUCTIONS ============
    remission_months = models.FloatField(
        blank=True, 
        null=True,
        help_text="Remission months granted"
    )
    reduction_months = models.FloatField(
        blank=True, 
        null=True,
        help_text="Additional reduction months"
    )
    reduction_reason = models.CharField(
        max_length=200,
        blank=True,
        help_text="Reason for reduction"
    )
    amnesty_earned = models.CharField(
        max_length=100,
        blank=True,
        help_text="Amnesty earned"
    )
    sentence_served = models.CharField(
        max_length=100,
        blank=True,
        help_text="Time served so far"
    )
    pre_trial_period = models.CharField(
        max_length=100,
        blank=True,
        help_text="Pre-trial period"
    )
    
    # ============ LOCATION/ADDRESS ============
    village = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Village/Town"
    )
    chief = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Chief/Area"
    )
    district = models.CharField(
        max_length=200, 
        blank=True,
        help_text="District"
    )
    region_location = models.CharField(
        max_length=100,
        blank=True,
        help_text="Region"
    )
    country = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Country"
    )
    nationality = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Nationality"
    )
    home_location = models.CharField(
        max_length=300,
        blank=True,
        help_text="Home location/address"
    )
    
    # ============ ADDITIONAL IDENTIFICATION ============
    national_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="National ID number"
    )
    passport_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="Passport number"
    )
    driving_license = models.CharField(
        max_length=50,
        blank=True,
        help_text="Driving license number"
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Phone number"
    )
    
    # ============ PREVIOUS CONVICTIONS ============
    previous_conviction_particulars = models.TextField(
        blank=True,
        help_text="Details of previous convictions"
    )
    previous_conviction_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of previous convictions"
    )
    is_recidivist = models.BooleanField(
        default=False,
        help_text="Whether the prisoner is a recidivist"
    )
    
    # ============ CONDUCT AND BEHAVIOR ============
    conduct = models.CharField(
        max_length=100,
        blank=True,
        help_text="Conduct rating/status"
    )
    behavior_rating = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('excellent', 'Excellent'),
            ('good', 'Good'),
            ('satisfactory', 'Satisfactory'),
            ('poor', 'Poor'),
            ('bad', 'Bad'),
        ],
        help_text="Behavior rating"
    )
    
    # ============ MEDICAL AND SPECIAL CATEGORIES ============
    is_chronically_ill = models.BooleanField(
        default=False,
        help_text="Whether the prisoner is chronically ill"
    )
    illness_description = models.CharField(
        max_length=300,
        blank=True,
        help_text="Description of illness"
    )
    is_pregnant = models.BooleanField(
        default=False,
        help_text="Whether the prisoner is pregnant"
    )
    gestation_period = models.CharField(
        max_length=50,
        blank=True,
        help_text="Gestation period (months)"
    )
    is_elderly = models.BooleanField(
        default=False,
        help_text="Whether the prisoner is elderly (70+)"
    )
    
    # ============ CHILDREN INFORMATION ============
    has_children = models.BooleanField(
        default=False,
        help_text="Whether the prisoner has children"
    )
    children_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of children"
    )
    child_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Name of child"
    )
    child_age = models.PositiveIntegerField(
        blank=True, 
        null=True,
        help_text="Age of child"
    )
    child_sex = models.CharField(
        max_length=10,
        blank=True,
        help_text="Sex of child"
    )
    children_details = models.TextField(
        blank=True,
        help_text="Detailed information about children"
    )
    
    # ============ ARREST AND AUTHORITY ============
    arresting_authority = models.CharField(
        max_length=200,
        blank=True,
        help_text="Arresting authority/officer"
    )
    date_of_arrest = models.DateField(
        blank=True, 
        null=True,
        help_text="Date of arrest"
    )
    place_of_arrest = models.CharField(
        max_length=200,
        blank=True,
        help_text="Place of arrest"
    )
    
    # ============ ADDITIONAL FIELDS ============
    cell_block = models.CharField(
        max_length=50,
        blank=True,
        help_text="Cell block"
    )
    cell_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="Cell number"
    )
    prisoner_type = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('convicted', 'Convicted'),
            ('remand', 'Remand'),
            ('pending', 'Pending'),
            ('foreigner', 'Foreigner'),
            ('special', 'Special'),
        ],
        help_text="Type of prisoner"
    )
    security_level = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('maximum', 'Maximum'),
        ],
        help_text="Security level"
    )
    
    # ============ REMARKS ============
    remarks = models.TextField(
        blank=True,
        help_text="General remarks"
    )
    special_remarks = models.TextField(
        blank=True,
        help_text="Special remarks"
    )
    
    # ============ ADDITIONAL DATA ============
    additional_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional data fields (key-value pairs)"
    )
    
    # ============ AUDIT ============
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this record was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this record was last updated"
    )
    
    # ============ META OPTIONS ============
    class Meta:
        verbose_name = "Inmate Return Data"
        verbose_name_plural = "Inmate Return Data"
        ordering = ['inmate_return', 'row_number', 'serial_no']
        indexes = [
            models.Index(fields=['inmate_return', 'row_number']),
            models.Index(fields=['prisoner_number']),
            models.Index(fields=['full_name']),
            models.Index(fields=['offense']),
            models.Index(fields=['sex']),
            models.Index(fields=['district']),
            models.Index(fields=['nationality']),
            models.Index(fields=['prisoner_class']),
        ]
    
    # ============ STRING REPRESENTATION ============
    def __str__(self):
        return f"{self.inmate_return.title} - Row {self.row_number} ({self.full_name or 'Unknown'})"
    
    # ============ DATA ACCESS ============
    def get_full_name(self):
        """Get full name with proper formatting"""
        if self.full_name:
            return self.full_name
        parts = [self.first_name, self.middle_name, self.surname]
        return ' '.join([p for p in parts if p])
    
    def get_data_dict(self):
        """Return all data as a dictionary"""
        data = {}
        for field in self._meta.fields:
            field_name = field.name
            if field_name not in ['id', 'inmate_return', 'additional_data', 'created_at', 'updated_at']:
                value = getattr(self, field_name)
                if value:
                    if isinstance(value, (date, datetime)):
                        data[field_name] = value.isoformat()
                    else:
                        data[field_name] = value
        if self.additional_data:
            data.update(self.additional_data)
        return data
    
    def get_age_group(self):
        """Get age group for this prisoner"""
        if not self.age:
            return 'Unknown'
        if self.age <= 18:
            return '0-18'
        elif self.age <= 30:
            return '19-30'
        elif self.age <= 45:
            return '31-45'
        elif self.age <= 60:
            return '46-60'
        else:
            return '61+'
    
    def get_sex_display(self):
        """Get human-readable sex display"""
        return dict(self._meta.get_field('sex').choices).get(self.sex, self.sex)
    
    def get_prisoner_type_display(self):
        """Get human-readable prisoner type"""
        return dict(self._meta.get_field('prisoner_type').choices).get(self.prisoner_type, self.prisoner_type)
    
    # ============ VALIDATION ============
    def clean(self):
        """Validate the model"""
        # Validate dates
        if self.date_of_birth and self.age:
            calculated_age = (date.today() - self.date_of_birth).days // 365
            if abs(calculated_age - self.age) > 5:
                # Raise warning but allow it (data might be approximate)
                pass
        
        # Validate age range
        if self.age and (self.age < 0 or self.age > 150):
            raise ValidationError({'age': 'Age must be between 0 and 150'})
        
        # Validate sentence
        if self.sentence_months and self.sentence_months < 0:
            raise ValidationError({'sentence_months': 'Sentence must be non-negative'})
    
    def save(self, *args, **kwargs):
        """Save with additional processing"""
        # Auto-calculate some fields
        if self.date_of_birth and not self.age:
            today = date.today()
            self.age = (today - self.date_of_birth).days // 365
        
        # Auto-set prisoner class based on other fields
        if not self.prisoner_class:
            if self.is_convicted:
                self.prisoner_class = 'convicted'
            elif self.is_remand:
                self.prisoner_class = 'remand'
        
        # Auto-set recidivist flag
        if self.previous_conviction_count > 0:
            self.is_recidivist = True
        
        # Auto-set elderly flag
        if self.age and self.age >= 70:
            self.is_elderly = True
        
        super().save(*args, **kwargs)



class InmateReturnData(models.Model):
    """Structured data for inmate returns extracted from CSV/Excel uploads"""
    
    inmate_return = models.ForeignKey(
        InmateReturn, 
        on_delete=models.CASCADE, 
        related_name='data_rows'
    )
    
    # Common fields for all return types
    serial_no = models.IntegerField(default=0)
    prisoner_number = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    first_name = models.CharField(max_length=100, blank=True, null=True)
    surname = models.CharField(max_length=100, blank=True, null=True)
    full_name = models.CharField(max_length=200, blank=True, null=True, db_index=True)
    sex = models.CharField(max_length=10, blank=True, null=True, db_index=True)
    age = models.IntegerField(blank=True, null=True, db_index=True)
    offense = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    
    # Location/address fields
    village = models.CharField(max_length=100, blank=True, null=True)
    chief = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    country = models.CharField(max_length=50, blank=True, null=True)
    nationality = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    
    # Court/legal fields
    court = models.CharField(max_length=100, blank=True, null=True)
    case_no = models.CharField(max_length=100, blank=True, null=True)
    sentence_months = models.FloatField(blank=True, null=True)
    date_of_committal = models.DateField(blank=True, null=True)
    date_of_admission = models.DateField(blank=True, null=True)
    date_of_conviction = models.DateField(blank=True, null=True)
    release_date_without_remission = models.DateField(blank=True, null=True)
    release_date_with_remission = models.DateField(blank=True, null=True)
    expected_date_release = models.DateField(blank=True, null=True)
    
    # Remand specific
    arresting_authority = models.CharField(max_length=100, blank=True, null=True)
    last_court_appearance = models.DateField(blank=True, null=True)
    judge_name = models.CharField(max_length=100, blank=True, null=True)
    case_status = models.CharField(max_length=100, blank=True, null=True)
    pre_trial_period = models.CharField(max_length=50, blank=True, null=True)
    
    # Pardon specific
    sentence_served = models.CharField(max_length=50, blank=True, null=True)
    amnesty_earned = models.CharField(max_length=100, blank=True, null=True)
    previous_conviction_particulars = models.TextField(blank=True, null=True)
    conduct = models.CharField(max_length=50, blank=True, null=True)
    
    # Children accompanying mothers
    child_name = models.CharField(max_length=200, blank=True, null=True)
    child_age = models.IntegerField(blank=True, null=True)
    child_sex = models.CharField(max_length=10, blank=True, null=True)
    gestation_period = models.CharField(max_length=50, blank=True, null=True)
    
    # General
    remarks = models.TextField(blank=True, null=True)
    
    # Metadata
    row_number = models.IntegerField(default=0)
    imported_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Additional JSON field for any extra data not covered
    extra_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = "Inmate Return Data"
        verbose_name_plural = "Inmate Return Data"
        ordering = ['inmate_return', 'serial_no', 'row_number']
        indexes = [
            models.Index(fields=['inmate_return', 'prisoner_number']),
            models.Index(fields=['inmate_return', 'serial_no']),
            models.Index(fields=['inmate_return', 'full_name']),
            models.Index(fields=['inmate_return', 'offense']),
            models.Index(fields=['inmate_return', 'sex']),
            models.Index(fields=['inmate_return', 'nationality']),
            models.Index(fields=['inmate_return', 'district']),
        ]
    
    def __str__(self):
        return f"{self.inmate_return.title} - Row {self.row_number} ({self.full_name or self.prisoner_number or 'No Name'})"
    
    def get_display_name(self):
        """Get the best available name"""
        if self.full_name:
            return self.full_name
        if self.first_name and self.surname:
            return f"{self.first_name} {self.surname}"
        return self.prisoner_number or "Unknown"
    
    def get_age_display(self):
        """Get age with suffix"""
        if self.age:
            return f"{self.age} years"
        return "Unknown"
    
    def get_sex_display(self):
        """Get full sex display"""
        if self.sex:
            if self.sex.lower() in ['m', 'male']:
                return 'Male'
            elif self.sex.lower() in ['f', 'female']:
                return 'Female'
        return self.sex or "Unknown"


class ReturnTemplate(models.Model):
    """Predefined templates for different return types"""
    
    RETURN_TYPE_CHOICES = InmateReturn.RETURN_TYPE_CHOICES
    
    name = models.CharField(max_length=100)
    return_type = models.CharField(max_length=50, choices=RETURN_TYPE_CHOICES, unique=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    
    # Column definitions as JSON
    columns = models.JSONField(
        default=list, 
        help_text="List of column definitions with key, header, and type"
    )
    
    # Sample data for demonstration
    sample_data = models.JSONField(default=list, blank=True, help_text="Sample data for template")
    
    # Column groups for better organization
    column_groups = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Group columns for display purposes"
    )
    
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False, help_text="Whether this is the default template for this type")
    
    # Version tracking
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_templates'
    )
    
    class Meta:
        verbose_name = "Return Template"
        verbose_name_plural = "Return Templates"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.get_return_type_display()}"
    
    def get_column_headers(self):
        """Get just the column headers from the columns definition"""
        return [col.get('header', col.get('key', '')) for col in self.columns]
    
    def get_column_keys(self):
        """Get all column keys"""
        return [col['key'] for col in self.columns if 'key' in col]
    
    def get_required_columns(self):
        """Get columns marked as required"""
        return [col for col in self.columns if col.get('required', False)]
    
    def get_column_by_key(self, key):
        """Get a column definition by its key"""
        for col in self.columns:
            if col.get('key') == key:
                return col
        return None
    
    def get_field_mapping(self):
        """Get mapping of CSV headers to model fields"""
        mapping = {}
        for col in self.columns:
            header = col.get('header', '').lower().strip()
            key = col.get('key')
            if header and key:
                mapping[header] = key
        return mapping
    
    def to_dict(self):
        """Convert template to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'return_type': self.return_type,
            'description': self.description,
            'columns': self.columns,
            'column_headers': self.get_column_headers(),
            'is_active': self.is_active,
        }
    
    def validate_data_row(self, row_data):
        """Validate a data row against the template"""
        errors = []
        required_cols = self.get_required_columns()
        
        for col in required_cols:
            key = col.get('key')
            if key and not row_data.get(key):
                errors.append(f"Missing required field: {col.get('header', key)}")
        
        return errors
    
    def create_sample_data(self):
        """Create sample data for this template"""
        if not self.sample_data:
            # Generate sample data based on columns
            sample = []
            for i in range(1, 4):
                row = {}
                for col in self.columns:
                    key = col.get('key')
                    if key:
                        # Generate sample values based on field type
                        field_type = col.get('type', 'string')
                        if field_type == 'number':
                            row[key] = i * 10
                        elif field_type == 'date':
                            row[key] = f"2024-01-{i:02d}"
                        elif field_type == 'string':
                            if key == 'serial_no':
                                row[key] = i
                            elif key == 'prisoner_number':
                                row[key] = f"P-{i:04d}"
                            elif key == 'full_name':
                                row[key] = f"Sample Prisoner {i}"
                            elif key == 'sex':
                                row[key] = 'M' if i % 2 == 1 else 'F'
                            elif key == 'age':
                                row[key] = 20 + i * 5
                            else:
                                row[key] = f"Sample {key.replace('_', ' ').title()} {i}"
                        else:
                            row[key] = f"Sample {i}"
                sample.append(row)
            self.sample_data = sample
            self.save(update_fields=['sample_data'])
        
        return self.sample_data


def create_default_templates():
    """Create all default return templates"""
    from django.db import transaction
    
    templates = [
        {
            'name': 'Convicted Inmates Return',
            'return_type': 'convicted',
            'description': 'Return for convicted inmates held at the station for a specific month',
            'columns': [
                {'key': 'serial_no', 'header': 'Ser. No.', 'type': 'number', 'required': True},
                {'key': 'prisoner_number', 'header': 'Pri. No.', 'type': 'string', 'required': True},
                {'key': 'full_name', 'header': 'Names', 'type': 'string', 'required': True},
                {'key': 'village', 'header': 'Village', 'type': 'string'},
                {'key': 'chief', 'header': 'T/A', 'type': 'string'},
                {'key': 'district', 'header': 'D.', 'type': 'string'},
                {'key': 'sex', 'header': 'Sex', 'type': 'string'},
                {'key': 'age', 'header': 'Age', 'type': 'number'},
                {'key': 'offense', 'header': 'Offence', 'type': 'string'},
                {'key': 'court', 'header': 'Court/Case No', 'type': 'string'},
                {'key': 'sentence_months', 'header': 'Sent.', 'type': 'number'},
                {'key': 'date_of_committal', 'header': 'Date of Commital', 'type': 'date'},
                {'key': 'release_date_without_remission', 'header': 'Expiry Date of Release Without Remission', 'type': 'date'},
                {'key': 'release_date_with_remission', 'header': 'Expiry Date of Release With Rem.', 'type': 'date'},
            ],
            'is_default': True,
        },
        {
            'name': 'Due Discharge',
            'return_type': 'discharge',
            'description': 'Due discharge list for the month',
            'columns': [
                {'key': 'serial_no', 'header': 'S/No.', 'type': 'number', 'required': True},
                {'key': 'prisoner_number', 'header': 'PRIS. No.', 'type': 'string', 'required': True},
                {'key': 'full_name', 'header': 'NAME', 'type': 'string', 'required': True},
                {'key': 'village', 'header': 'Village', 'type': 'string'},
                {'key': 'chief', 'header': 'T/A', 'type': 'string'},
                {'key': 'district', 'header': 'D.', 'type': 'string'},
                {'key': 'sex', 'header': 'SEX', 'type': 'string'},
                {'key': 'age', 'header': 'AGE', 'type': 'number'},
                {'key': 'offense', 'header': 'OFFENCE', 'type': 'string'},
                {'key': 'court', 'header': 'COURT/ CASE No', 'type': 'string'},
                {'key': 'sentence_months', 'header': 'SENT.', 'type': 'number'},
                {'key': 'date_of_committal', 'header': 'DATE OF CONV.', 'type': 'date'},
                {'key': 'amnesty_earned', 'header': 'AMNESTY EARNED', 'type': 'string'},
                {'key': 'expected_date_release', 'header': 'DUE DATE', 'type': 'date'},
                {'key': 'remarks', 'header': 'REMARKS i.e loss of remission', 'type': 'string'},
            ],
            'is_default': True,
        },
        {
            'name': 'Remand Murder Prisoners',
            'return_type': 'remand_murder',
            'description': 'Return for remand murder prisoners held at the station',
            'columns': [
                {'key': 'serial_no', 'header': 'Ser. No.', 'type': 'number', 'required': True},
                {'key': 'prisoner_number', 'header': 'PRIS. NO', 'type': 'string', 'required': True},
                {'key': 'full_name', 'header': 'NAME', 'type': 'string', 'required': True},
                {'key': 'village', 'header': 'Village', 'type': 'string'},
                {'key': 'chief', 'header': 'T/A', 'type': 'string'},
                {'key': 'district', 'header': 'D.', 'type': 'string'},
                {'key': 'age', 'header': 'AGE', 'type': 'number'},
                {'key': 'sex', 'header': 'SEX', 'type': 'string'},
                {'key': 'offense', 'header': 'OFFENCE', 'type': 'string'},
                {'key': 'court', 'header': 'COURT/ CASE No', 'type': 'string'},
                {'key': 'date_of_admission', 'header': 'DATE OF ADMISSION', 'type': 'date'},
                {'key': 'arresting_authority', 'header': 'ARRESTING AUTHORITY', 'type': 'string'},
                {'key': 'last_court_appearance', 'header': 'LAST COURT APPEARANCE', 'type': 'date'},
                {'key': 'judge_name', 'header': 'JUDGE NAME', 'type': 'string'},
                {'key': 'case_status', 'header': 'STATUS', 'type': 'string'},
            ],
            'is_default': True,
        },
        {
            'name': 'Convicted Foreigners Return',
            'return_type': 'convicted_foreigners',
            'description': 'Return for convicted foreigners held at the station',
            'columns': [
                {'key': 'serial_no', 'header': 'SER. NO.', 'type': 'number', 'required': True},
                {'key': 'prisoner_number', 'header': 'PRIS. No', 'type': 'string', 'required': True},
                {'key': 'full_name', 'header': 'NAME', 'type': 'string', 'required': True},
                {'key': 'village', 'header': 'Village', 'type': 'string'},
                {'key': 'chief', 'header': 'T/A', 'type': 'string'},
                {'key': 'district', 'header': 'D.', 'type': 'string'},
                {'key': 'country', 'header': 'Country', 'type': 'string'},
                {'key': 'sex', 'header': 'SEX', 'type': 'string'},
                {'key': 'age', 'header': 'AGE', 'type': 'number'},
                {'key': 'offense', 'header': 'OFFENCE', 'type': 'string'},
                {'key': 'court', 'header': 'COURT', 'type': 'string'},
                {'key': 'sentence_months', 'header': 'SENTENCE', 'type': 'number'},
                {'key': 'date_of_conviction', 'header': 'DATE OF CONVICTION', 'type': 'date'},
                {'key': 'amnesty_earned', 'header': 'AMNESTY EARNED', 'type': 'string'},
                {'key': 'expected_date_release', 'header': 'EXPECTED DATE OF RELEASE', 'type': 'date'},
                {'key': 'remarks', 'header': 'REMARKS i.e loss of remission', 'type': 'string'},
            ],
            'is_default': True,
        },
        {
            'name': 'Foreign Remand Prisoners',
            'return_type': 'foreigners_remand',
            'description': 'Return for foreign remand prisoners held at the station',
            'columns': [
                {'key': 'serial_no', 'header': 'SER.NO.', 'type': 'number', 'required': True},
                {'key': 'prisoner_number', 'header': 'PRI.NO.', 'type': 'string', 'required': True},
                {'key': 'full_name', 'header': 'NAME', 'type': 'string', 'required': True},
                {'key': 'village', 'header': 'Village', 'type': 'string'},
                {'key': 'chief', 'header': 'T/A', 'type': 'string'},
                {'key': 'district', 'header': 'D.', 'type': 'string'},
                {'key': 'country', 'header': 'Country', 'type': 'string'},
                {'key': 'sex', 'header': 'SEX', 'type': 'string'},
                {'key': 'age', 'header': 'AGE', 'type': 'number'},
                {'key': 'offense', 'header': 'OFFENCE', 'type': 'string'},
                {'key': 'court', 'header': 'COURT AND CASE NO.', 'type': 'string'},
                {'key': 'date_of_admission', 'header': 'DATE OF ADMISSION', 'type': 'date'},
                {'key': 'arresting_authority', 'header': 'ARRESTING AUTHORITY', 'type': 'string'},
                {'key': 'pre_trial_period', 'header': 'PRE-TRIAL PERIOD', 'type': 'string'},
                {'key': 'remarks', 'header': 'REMARKS', 'type': 'string'},
            ],
            'is_default': True,
        },
        {
            'name': 'General Remandees Return',
            'return_type': 'general_remandees',
            'description': 'Return for general remandees held at the station',
            'columns': [
                {'key': 'serial_no', 'header': 'SER. NO.', 'type': 'number', 'required': True},
                {'key': 'full_name', 'header': 'NAME', 'type': 'string', 'required': True},
                {'key': 'village', 'header': 'Village', 'type': 'string'},
                {'key': 'chief', 'header': 'T/A', 'type': 'string'},
                {'key': 'district', 'header': 'D.', 'type': 'string'},
                {'key': 'sex', 'header': 'SEX', 'type': 'string'},
                {'key': 'age', 'header': 'AGE', 'type': 'number'},
                {'key': 'offense', 'header': 'OFFENCE', 'type': 'string'},
                {'key': 'court', 'header': 'COURT/ CASE No', 'type': 'string'},
                {'key': 'date_of_admission', 'header': 'DATE OF ADMISSION', 'type': 'date'},
                {'key': 'arresting_authority', 'header': 'ARRESTING AUTHORITY', 'type': 'string'},
                {'key': 'last_court_appearance', 'header': 'LAST COURT APPEARANCE', 'type': 'date'},
                {'key': 'case_status', 'header': 'CASE STATUS', 'type': 'string'},
            ],
            'is_default': True,
        },
        {
            'name': 'Normal Pardon List',
            'return_type': 'lockup',
            'description': 'List of convicted prisoners to be considered for normal pardon',
            'columns': [
                {'key': 'serial_no', 'header': 'NO', 'type': 'number', 'required': True},
                {'key': 'prisoner_number', 'header': 'PRIS NO:', 'type': 'string', 'required': True},
                {'key': 'full_name', 'header': 'NAME', 'type': 'string', 'required': True},
                {'key': 'village', 'header': 'Village', 'type': 'string'},
                {'key': 'chief', 'header': 'T/A', 'type': 'string'},
                {'key': 'district', 'header': 'D.', 'type': 'string'},
                {'key': 'sex', 'header': 'SEX', 'type': 'string'},
                {'key': 'age', 'header': 'AGE', 'type': 'number'},
                {'key': 'offense', 'header': 'OFFENCE', 'type': 'string'},
                {'key': 'court', 'header': 'COURT', 'type': 'string'},
                {'key': 'sentence_months', 'header': 'SENTENCE', 'type': 'number'},
                {'key': 'date_of_committal', 'header': 'DOC', 'type': 'date'},
                {'key': 'sentence_served', 'header': 'SENT. SERVED', 'type': 'string'},
                {'key': 'amnesty_earned', 'header': 'AMNESTY EARNED', 'type': 'string'},
                {'key': 'expected_date_release', 'header': 'EXPECTED DATE OF RELEASE', 'type': 'date'},
                {'key': 'previous_conviction_particulars', 'header': 'PARTICULARS OF PREVIOUS CONVICTION', 'type': 'string'},
                {'key': 'conduct', 'header': 'CONDUCT', 'type': 'string'},
            ],
            'is_default': True,
        },
        {
            'name': 'Chronically Ill Convicted Inmates',
            'return_type': 'chronically_ill',
            'description': 'List of chronically ill convicted inmates proposed for pardon',
            'columns': [
                {'key': 'serial_no', 'header': 'NO', 'type': 'number', 'required': True},
                {'key': 'prisoner_number', 'header': 'PRIS NO:', 'type': 'string', 'required': True},
                {'key': 'full_name', 'header': 'NAME', 'type': 'string', 'required': True},
                {'key': 'village', 'header': 'Village', 'type': 'string'},
                {'key': 'chief', 'header': 'T/A', 'type': 'string'},
                {'key': 'district', 'header': 'D.', 'type': 'string'},
                {'key': 'sex', 'header': 'SEX', 'type': 'string'},
                {'key': 'age', 'header': 'AGE', 'type': 'number'},
                {'key': 'offense', 'header': 'OFFENCE', 'type': 'string'},
                {'key': 'court', 'header': 'COURT', 'type': 'string'},
                {'key': 'sentence_months', 'header': 'SENTENCE', 'type': 'number'},
                {'key': 'date_of_committal', 'header': 'DOC', 'type': 'date'},
                {'key': 'amnesty_earned', 'header': 'AMNESTY EARNED', 'type': 'string'},
                {'key': 'expected_date_release', 'header': 'EXPECTED DATE OF RELEASE', 'type': 'date'},
                {'key': 'previous_conviction_particulars', 'header': 'PARTICULARS OF PREVIOUS CONVICTION', 'type': 'string'},
                {'key': 'conduct', 'header': 'CONDUCT', 'type': 'string'},
            ],
            'is_default': True,
        },
        {
            'name': 'Elderly Prisoners (70+ Years)',
            'return_type': 'convicted_elderly_prisoners',
            'description': 'List of convicted elderly inmates aged 70 years and above proposed for pardon',
            'columns': [
                {'key': 'serial_no', 'header': 'NO', 'type': 'number', 'required': True},
                {'key': 'prisoner_number', 'header': 'PRIS NO:', 'type': 'string', 'required': True},
                {'key': 'full_name', 'header': 'NAME', 'type': 'string', 'required': True},
                {'key': 'village', 'header': 'Village', 'type': 'string'},
                {'key': 'chief', 'header': 'T/A', 'type': 'string'},
                {'key': 'district', 'header': 'D.', 'type': 'string'},
                {'key': 'sex', 'header': 'SEX', 'type': 'string'},
                {'key': 'age', 'header': 'AGE', 'type': 'number'},
                {'key': 'offense', 'header': 'OFFENCE', 'type': 'string'},
                {'key': 'court', 'header': 'COURT', 'type': 'string'},
                {'key': 'sentence_months', 'header': 'SENTENCE', 'type': 'number'},
                {'key': 'date_of_committal', 'header': 'DOC', 'type': 'date'},
                {'key': 'sentence_served', 'header': 'SENT. SERVED', 'type': 'string'},
                {'key': 'amnesty_earned', 'header': 'AMNESTY EARNED', 'type': 'string'},
                {'key': 'expected_date_release', 'header': 'EXPECTED DATE OF RELEASE', 'type': 'date'},
                {'key': 'previous_conviction_particulars', 'header': 'PARTICULARS OF PREVIOUS CONVICTION', 'type': 'string'},
                {'key': 'conduct', 'header': 'CONDUCT', 'type': 'string'},
            ],
            'is_default': True,
        },
        {
            'name': 'Discharged After 6 Months Reduction',
            'return_type': 'discharged_prisoners_after_reductions',
            'description': 'Prisoners who have been discharged after effecting 6 months reduction',
            'columns': [
                {'key': 'serial_no', 'header': 'NO', 'type': 'number', 'required': True},
                {'key': 'prisoner_number', 'header': 'PRIS NO:', 'type': 'string', 'required': True},
                {'key': 'full_name', 'header': 'NAME', 'type': 'string', 'required': True},
                {'key': 'village', 'header': 'Village', 'type': 'string'},
                {'key': 'chief', 'header': 'T/A', 'type': 'string'},
                {'key': 'district', 'header': 'D.', 'type': 'string'},
                {'key': 'sex', 'header': 'SEX', 'type': 'string'},
                {'key': 'age', 'header': 'AGE', 'type': 'number'},
                {'key': 'offense', 'header': 'OFFENCE', 'type': 'string'},
                {'key': 'court', 'header': 'COURT', 'type': 'string'},
                {'key': 'sentence_months', 'header': 'SENTENCE', 'type': 'number'},
                {'key': 'date_of_committal', 'header': 'DOC', 'type': 'date'},
                {'key': 'amnesty_earned', 'header': 'AMNESTY EARNED', 'type': 'string'},
                {'key': 'expected_date_release', 'header': 'EXPECTED DATE OF RELEASE', 'type': 'date'},
                {'key': 'release_date_with_remission', 'header': 'EDR AFTER AMNESTY', 'type': 'date'},
            ],
            'is_default': True,
        },
        {
            'name': 'Children Accompanying Mothers',
            'return_type': 'children_accompanying_their_mothers',
            'description': 'Return for children accompanying their mothers in prison',
            'columns': [
                {'key': 'serial_no', 'header': 'S/N', 'type': 'number', 'required': True},
                {'key': 'prisoner_number', 'header': 'PRI NO.', 'type': 'string', 'required': True},
                {'key': 'full_name', 'header': 'NAME', 'type': 'string', 'required': True},
                {'key': 'village', 'header': 'Village', 'type': 'string'},
                {'key': 'chief', 'header': 'T/A', 'type': 'string'},
                {'key': 'district', 'header': 'D.', 'type': 'string'},
                {'key': 'sex', 'header': 'SEX', 'type': 'string'},
                {'key': 'age', 'header': 'AGE', 'type': 'number'},
                {'key': 'offense', 'header': 'OFFENCE', 'type': 'string'},
                {'key': 'court', 'header': 'COURT CASE NO.', 'type': 'string'},
                {'key': 'sentence_months', 'header': 'SENTENCE', 'type': 'number'},
                {'key': 'date_of_conviction', 'header': 'DATE OF CONV.', 'type': 'date'},
                {'key': 'expected_date_release', 'header': 'E.D.R', 'type': 'date'},
                {'key': 'child_name', 'header': 'NAME OF A CHILD', 'type': 'string'},
                {'key': 'child_age', 'header': 'AGE', 'type': 'number'},
                {'key': 'child_sex', 'header': 'SEX', 'type': 'string'},
            ],
            'is_default': True,
        },
        {
            'name': 'Convicted Pregnant Prisoners',
            'return_type': 'convicted_pregnant_inmates',
            'description': 'Return for convicted pregnant prisoners',
            'columns': [
                {'key': 'prisoner_number', 'header': 'PRIS NO:', 'type': 'string', 'required': True},
                {'key': 'full_name', 'header': 'NAME', 'type': 'string', 'required': True},
                {'key': 'village', 'header': 'Village', 'type': 'string'},
                {'key': 'chief', 'header': 'T/A', 'type': 'string'},
                {'key': 'district', 'header': 'D.', 'type': 'string'},
                {'key': 'sex', 'header': 'SEX', 'type': 'string'},
                {'key': 'age', 'header': 'AGE', 'type': 'number'},
                {'key': 'offense', 'header': 'OFFENCE', 'type': 'string'},
                {'key': 'court', 'header': 'COURT', 'type': 'string'},
                {'key': 'sentence_months', 'header': 'SENTENCE', 'type': 'number'},
                {'key': 'date_of_committal', 'header': 'DOC', 'type': 'date'},
                {'key': 'amnesty_earned', 'header': 'AMNESTY EARNED', 'type': 'string'},
                {'key': 'expected_date_release', 'header': 'EXPECTED DATE OF RELEASE', 'type': 'date'},
                {'key': 'gestation_period', 'header': 'GESTATION PERIOD', 'type': 'string'},
                {'key': 'remarks', 'header': 'REMARKS', 'type': 'string'},
            ],
            'is_default': True,
        },
        {
            'name': 'Pregnant Remand (Murder)',
            'return_type': 'remandee_preg_inmates_murder',
            'description': 'Return for pregnant remand (murder) inmates',
            'columns': [
                {'key': 'serial_no', 'header': 'S/N', 'type': 'number', 'required': True},
                {'key': 'prisoner_number', 'header': 'REM NO.', 'type': 'string', 'required': True},
                {'key': 'full_name', 'header': 'NAME', 'type': 'string', 'required': True},
                {'key': 'village', 'header': 'Village', 'type': 'string'},
                {'key': 'chief', 'header': 'T/A', 'type': 'string'},
                {'key': 'district', 'header': 'D.', 'type': 'string'},
                {'key': 'sex', 'header': 'SEX', 'type': 'string'},
                {'key': 'age', 'header': 'AGE', 'type': 'number'},
                {'key': 'offense', 'header': 'OFFENCE', 'type': 'string'},
                {'key': 'court', 'header': 'COURT/CASE NO.', 'type': 'string'},
                {'key': 'gestation_period', 'header': 'GESTATION PERIOD', 'type': 'string'},
                {'key': 'remarks', 'header': 'REMARKS', 'type': 'string'},
            ],
            'is_default': True,
        },
        {
            'name': 'Children Accompanying Mothers on Homicide',
            'return_type': 'children_accompanying_their_mothers_on_homocide',
            'description': 'Return for children accompanying their mothers on homicide and general remand',
            'columns': [
                {'key': 'serial_no', 'header': 'S/N', 'type': 'number', 'required': True},
                {'key': 'prisoner_number', 'header': 'PRI NO.', 'type': 'string', 'required': True},
                {'key': 'full_name', 'header': 'NAME', 'type': 'string', 'required': True},
                {'key': 'village', 'header': 'Village', 'type': 'string'},
                {'key': 'chief', 'header': 'T/A', 'type': 'string'},
                {'key': 'district', 'header': 'D.', 'type': 'string'},
                {'key': 'sex', 'header': 'SEX', 'type': 'string'},
                {'key': 'age', 'header': 'AGE', 'type': 'number'},
                {'key': 'offense', 'header': 'OFFENCE', 'type': 'string'},
                {'key': 'court', 'header': 'COURT CASE NO.', 'type': 'string'},
                {'key': 'date_of_committal', 'header': 'D.O.C', 'type': 'date'},
                {'key': 'child_name', 'header': 'NAME OF A CHILD', 'type': 'string'},
                {'key': 'child_age', 'header': 'AGE', 'type': 'number'},
                {'key': 'child_sex', 'header': 'SEX', 'type': 'string'},
            ],
            'is_default': True,
        },
        {
            'name': 'Pending Cases Return',
            'return_type': 'pending',
            'description': 'Return for pending cases',
            'columns': [
                {'key': 'serial_no', 'header': 'S/No.', 'type': 'number', 'required': True},
                {'key': 'prisoner_number', 'header': 'PRI NO.', 'type': 'string', 'required': True},
                {'key': 'full_name', 'header': 'NAME', 'type': 'string', 'required': True},
                {'key': 'offense', 'header': 'OFFENCE', 'type': 'string'},
                {'key': 'court', 'header': 'COURT/CASE NO.', 'type': 'string'},
                {'key': 'date_of_admission', 'header': 'DATE OF ADMISSION', 'type': 'date'},
                {'key': 'case_status', 'header': 'STATUS', 'type': 'string'},
                {'key': 'remarks', 'header': 'REMARKS', 'type': 'string'},
            ],
            'is_default': True,
        },
    ]
    
    with transaction.atomic():
        for template_data in templates:
            ReturnTemplate.objects.get_or_create(
                return_type=template_data['return_type'],
                defaults={
                    'name': template_data['name'],
                    'description': template_data['description'],
                    'columns': template_data['columns'],
                    'is_default': template_data.get('is_default', False),
                    'is_active': True,
                }
            )
    
    return ReturnTemplate.objects.count()

# ============ RATION MANAGEMENT MODELS ============

class RationItem(models.Model):
    UNIT_CHOICES = [
        ('kg', 'Kilograms (kg)'),
        ('bags', 'Bags'),
        ('pieces', 'Pieces'),
        ('liters', 'Liters (L)'),
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
    daily_consumption_per_prisoner_kg = models.DecimalField(
        max_digits=10, decimal_places=4, default=0.500,
        help_text="Daily consumption per prisoner in kg (used for automatic calculations)"
    )
    estimated_days_remaining = models.PositiveIntegerField(
        default=0,
        help_text="Estimated days ration will last based on current stock and prisoner count"
    )
    last_stock_update = models.DateTimeField(auto_now=True)
    last_consumption_date = models.DateField(blank=True, null=True)
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
        unique_together = ('name', 'prison_station')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.prison_station.name})"

    @property
    def is_low_stock(self):
        return self.current_stock_kg < self.low_stock_threshold_kg

    def get_current_prisoner_count(self):
        """Get current number of prisoners for this station"""
        from .models import Prisoner
        return Prisoner.objects.filter(
            prison_station=self.prison_station,
            is_active=True
        ).count()

    def calculate_estimated_days(self):
        """Calculate estimated days remaining based on current stock and prisoner count"""
        if self.current_stock_kg <= 0 or self.daily_consumption_per_prisoner_kg <= 0:
            return 0
        
        prisoner_count = self.get_current_prisoner_count()
        if prisoner_count == 0:
            return 0
        
        daily_total_consumption = self.daily_consumption_per_prisoner_kg * prisoner_count
        if daily_total_consumption <= 0:
            return 0
        
        days_remaining = self.current_stock_kg / daily_total_consumption
        return int(days_remaining)

    def update_estimated_days(self):
        """Update the estimated days remaining field"""
        self.estimated_days_remaining = self.calculate_estimated_days()
        self.save(update_fields=['estimated_days_remaining', 'last_stock_update'])

    def record_daily_consumption(self, auto=True):
        """
        Record daily consumption based on current prisoner count.
        If auto=True, uses daily_consumption_per_prisoner_kg * prisoner_count
        If auto=False, requires manual quantity entry
        """
        prisoner_count = self.get_current_prisoner_count()
        if prisoner_count == 0:
            return None
        
        if auto:
            quantity_used = self.daily_consumption_per_prisoner_kg * prisoner_count
        else:
            quantity_used = 0  # Would need manual input
        
        # Create consumption record
        consumption = RationConsumption.objects.create(
            item=self,
            consumption_date=timezone.now().date(),
            quantity_used_kg=quantity_used,
            num_prisoners_fed=prisoner_count,
            is_auto_calculated=auto
        )
        
        # Update stock
        self.current_stock_kg -= quantity_used
        self.last_consumption_date = timezone.now().date()
        self.save(update_fields=['current_stock_kg', 'last_consumption_date', 'last_stock_update'])
        
        # Update estimated days
        self.update_estimated_days()
        
        return consumption

class RationConsumption(models.Model):
    item = models.ForeignKey(RationItem, on_delete=models.CASCADE, related_name='consumptions')
    consumption_date = models.DateField(default=timezone.now)
    quantity_used_kg = models.DecimalField(
        max_digits=10, decimal_places=3,
        help_text="Quantity consumed in Kilograms (kg)",
        validators=[MinValueValidator(0.001)]
    )
    num_prisoners_fed = models.PositiveIntegerField(
        help_text="Number of prisoners (including children) fed with this ration on this day"
    )
    is_auto_calculated = models.BooleanField(
        default=False,
        help_text="Whether this consumption was automatically calculated based on prisoner count"
    )
    consumed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='rations_consumed')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ration Consumption"
        verbose_name_plural = "Ration Consumptions"
        ordering = ['-consumption_date', 'item__name']

    def clean(self):
        if self.item and self.quantity_used_kg is not None:
            if self.item.current_stock_kg is None:
                raise ValidationError(
                    {'quantity_used_kg': f"Current stock for {self.item.name} is not set (None). Cannot record consumption."}
                )
            if self.quantity_used_kg > self.item.current_stock_kg:
                raise ValidationError(
                    {'quantity_used_kg': f"Consumption amount ({self.quantity_used_kg} kg) exceeds current stock ({self.item.current_stock_kg} kg) for {self.item.name}."}
                )
        super().clean()

    def save(self, *args, **kwargs):
        # Deduct from stock when consumption is recorded
        if not self.pk:  # Only on creation
            if self.item and self.quantity_used_kg:
                self.item.current_stock_kg -= self.quantity_used_kg
                self.item.last_consumption_date = self.consumption_date
                self.item.save(update_fields=['current_stock_kg', 'last_consumption_date', 'last_stock_update'])
                # Update estimated days
                self.item.update_estimated_days()
        super().save(*args, **kwargs)

class RationProcurement(models.Model):
    item = models.ForeignKey(RationItem, on_delete=models.CASCADE, related_name='procurements')
    procurement_date = models.DateField(default=timezone.now)
    quantity_procured_kg = models.DecimalField(
        max_digits=10, decimal_places=3,
        help_text="Quantity procured in Kilograms (kg)",
        validators=[MinValueValidator(0.001)]
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
        # Add to stock when procurement is recorded
        if not self.pk:  # Only on creation
            if self.item and self.quantity_procured_kg:
                self.item.current_stock_kg += self.quantity_procured_kg
                self.item.save(update_fields=['current_stock_kg', 'last_stock_update'])
                # Update estimated days
                self.item.update_estimated_days()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Procured {self.quantity_procured_kg}kg of {self.item.name} on {self.procurement_date}"


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('medical_checkup', 'Medical Checkup Reminder'),
        ('near_release', 'Prisoner Near Release'),
        ('new_admission', 'New Prisoner Admission'),
        ('general', 'General Notification'),
    ]

    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='general')
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='medium')
    
    # Related objects (optional)
    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    medical_record = models.ForeignKey(MedicalRecord, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    
    # Target users
    target_users = models.ManyToManyField(User, related_name='notifications', blank=True)
    
    # Status tracking
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    read_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='read_notifications')
    
    # Metadata
    action_required = models.BooleanField(default=False)
    action_url = models.CharField(max_length=255, blank=True, null=True)
    due_date = models.DateField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.get_notification_type_display()}"

    def mark_as_read(self, user):
        """Mark notification as read by a specific user"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.read_by = user
            self.save(update_fields=['is_read', 'read_at', 'read_by'])

    def is_expired(self):
        """Check if notification has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False