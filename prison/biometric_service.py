# biometric_service.py

import base64
import hashlib
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple, List

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import get_user_model

# Get the User model
User = get_user_model()

# Import models
from .models import (
    Prisoner, 
    FingerprintMatch, 
    FingerprintDevice, 
    FingerprintAuditLog, 
    ActivityLog,
    PrisonStation
)

logger = logging.getLogger(__name__)


class FingerprintProcessor:
    """
    Handles fingerprint processing and matching operations.
    This is a wrapper around the fingerprint hardware SDK.
    """
    
    @staticmethod
    def capture_fingerprint(device_id: Optional[int] = None) -> Tuple[str, int, Dict]:
        """
        Capture fingerprint from the scanner.
        
        Args:
            device_id: Optional device identifier
        
        Returns:
            Tuple containing:
            - template_string: The captured fingerprint template
            - quality_score: Quality score (0-100)
            - metadata: Additional capture metadata
        """
        try:
            # This is where you'd call the actual fingerprint SDK
            # For testing/simulation:
            import random
            template = base64.b64encode(
                f"fingerprint_template_{random.randint(1000, 9999)}".encode()
            ).decode()
            quality = random.randint(60, 100)
            metadata = {
                'capture_method': 'simulated',
                'device': 'Integrated Scanner',
                'timestamp': datetime.now().isoformat()
            }
            
            return template, quality, metadata
            
        except Exception as e:
            logger.error(f"Fingerprint capture failed: {str(e)}")
            raise ValidationError(f"Failed to capture fingerprint: {str(e)}")

    @staticmethod
    def extract_features(template: str) -> Dict:
        """
        Extract feature vectors from fingerprint template for matching.
        
        Args:
            template: The fingerprint template string
        
        Returns:
            Dictionary containing extracted features
        """
        return {
            'hash': hashlib.sha256(template.encode()).hexdigest(),
            'template': template,
            'length': len(template)
        }

    @staticmethod
    def match_fingerprints(template1: str, template2: str) -> Tuple[float, bool]:
        """
        Compare two fingerprint templates.
        
        Args:
            template1: First fingerprint template
            template2: Second fingerprint template
        
        Returns:
            Tuple containing:
            - match_score: Similarity score (0-100)
            - is_match: Boolean indicating if templates match
        """
        # For testing/simulation:
        if template1 == template2:
            return 100.0, True
        
        # Simulate realistic matching for testing
        import random
        # Simple similarity based on string length and content
        if template1 and template2:
            len_sim = 1 - abs(len(template1) - len(template2)) / max(len(template1), len(template2), 1)
            base_score = len_sim * 50
        else:
            base_score = 0
        
        # Add some randomness for testing
        score = min(100, base_score + random.uniform(-30, 30))
        score = max(0, score)
        is_match = score >= 70.0
        
        return score, is_match

    @staticmethod
    def normalize_fingerprint(template: str) -> str:
        """
        Normalize a fingerprint template for consistent storage and comparison.
        
        Args:
            template: The fingerprint template string
        
        Returns:
            Normalized template string
        """
        return template.strip()


class BiometricService:
    """
    Service class for handling biometric operations in the prison system.
    """
    
    MATCH_THRESHOLD = 70.0  # 70% match threshold
    
    @staticmethod
    def check_recidivism(fingerprint_data: str, threshold: float = 85.0) -> Dict:
        """
        Check if a fingerprint belongs to a previous prisoner (recidivist).
        Returns: Dict with recidivism info
        """
        # Get ALL prisoners with fingerprints (including inactive ones)
        all_prisoners = Prisoner.objects.filter(
            fingerprint_template__isnull=False,
            fingerprint_template__gt=''
        ).select_related('prison_station')
        
        matches = []
        
        for prisoner in all_prisoners:
            try:
                score, is_match = FingerprintProcessor.match_fingerprints(
                    fingerprint_data,
                    prisoner.fingerprint_template
                )
                
                if is_match or score >= threshold:
                    matches.append({
                        'prisoner': prisoner,
                        'score': score,
                        'is_match': is_match
                    })
            except Exception as e:
                logger.error(f"Error matching fingerprint for prisoner {prisoner.id}: {str(e)}")
                continue
        
        # Sort by score descending
        matches.sort(key=lambda x: x['score'], reverse=True)
        
        if matches:
            best_match = matches[0]
            prisoner = best_match['prisoner']
            
            return {
                'is_recidivist': True,
                'matched_prisoner': prisoner,
                'match_score': best_match['score'],
                'previous_prisoner_number': prisoner.prisoner_number,
                'previous_full_name': prisoner.full_name,
                'previous_status': 'active' if prisoner.is_active else 'released',
                'previous_release_date': prisoner.date_released,
                'previous_class': prisoner.prisoner_class,
                'all_matches': matches[:3]  # Top 3 matches for reference
            }
        
        return {
            'is_recidivist': False,
            'matched_prisoner': None,
            'match_score': 0
        }
    
    @staticmethod
    def register_fingerprint(
        prisoner: Prisoner, 
        fingerprint_data: str, 
        quality_score: int, 
        captured_by: User,
        device_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Prisoner:
        """
        Register a prisoner's fingerprint with recidivism detection.
        """
        if not prisoner:
            raise ValueError("Prisoner is required")
        
        if not fingerprint_data:
            raise ValidationError("Fingerprint data is required")
        
        # Validate quality score
        if quality_score < 30:
            raise ValidationError(
                f"Fingerprint quality too low ({quality_score}%). Please try again."
            )
        
        # ===== CHECK FOR RECIDIVISM =====
        recidivism_check = BiometricService.check_recidivism(fingerprint_data, threshold=80.0)
        
        if recidivism_check['is_recidivist']:
            matched_prisoner = recidivism_check['matched_prisoner']
            
            # If the matched prisoner is the same as the current prisoner, skip recidivism
            if matched_prisoner.pk != prisoner.pk:
                # This fingerprint belongs to a previous prisoner
                raise ValidationError(
                    f"⚠️ RECIDIVISM DETECTED!\n\n"
                    f"This fingerprint matches a previous prisoner:\n"
                    f"Previous ID: {matched_prisoner.prisoner_number}\n"
                    f"Previous Name: {matched_prisoner.full_name}\n"
                    f"Match Confidence: {recidivism_check['match_score']:.1f}%\n"
                    f"Status: {'Active' if matched_prisoner.is_active else 'Released'}\n\n"
                    f"This person has been incarcerated before and should be flagged as a recidivist.\n"
                    f"Please review and confirm before proceeding."
                )
        
        # Extract features and generate hash
        features = FingerprintProcessor.extract_features(fingerprint_data)
        
        # Get device if provided
        device = None
        if device_id:
            try:
                device = FingerprintDevice.objects.get(id=device_id)
            except FingerprintDevice.DoesNotExist:
                pass
        
        # Update prisoner record
        with transaction.atomic():
            prisoner.fingerprint_template = fingerprint_data
            prisoner.fingerprint_hash = features['hash']
            prisoner.fingerprint_captured_at = timezone.now()
            prisoner.fingerprint_captured_by = captured_by
            prisoner.fingerprint_quality = quality_score
            prisoner.fingerprint_device = device
            
            # ===== MARK AS RECIDIVIST IF MATCH FOUND =====
            if recidivism_check['is_recidivist'] and matched_prisoner.pk != prisoner.pk:
                prisoner.is_recidivist = True
                prisoner.recidivism_detected_at = timezone.now()
                prisoner.recidivism_detected_by = captured_by
                prisoner.recidivism_notes = (
                    f"Recidivism detected via fingerprint match with "
                    f"{matched_prisoner.prisoner_number} ({matched_prisoner.full_name}) - "
                    f"Confidence: {recidivism_check['match_score']:.1f}%\n"
                    f"Previous status: {'Active' if matched_prisoner.is_active else 'Released'}"
                )
                
                # Add previous prisoner number to history
                if prisoner.previous_prisoner_numbers:
                    prisoner.previous_prisoner_numbers += f", {matched_prisoner.prisoner_number}"
                else:
                    prisoner.previous_prisoner_numbers = matched_prisoner.prisoner_number
                
                # Set first incarceration date if not set
                if not prisoner.first_incarceration_date:
                    prisoner.first_incarceration_date = matched_prisoner.date_admitted
                
                # Link the identities
                prisoner.previous_identities.add(matched_prisoner)
            
            # If this is the first fingerprint and not recidivist, mark as verified
            if not prisoner.is_identity_verified and not prisoner.is_recidivist:
                prisoner.is_identity_verified = True
                prisoner.identity_verified_at = timezone.now()
                prisoner.identity_verified_by = captured_by
                prisoner.identity_verification_notes = f"Verified during fingerprint registration with quality {quality_score}%"
            
            prisoner.save()
        
        # Log the registration
        FingerprintMatch.objects.create(
            searched_prisoner=prisoner,
            matched_prisoner=matched_prisoner if recidivism_check['is_recidivist'] else prisoner,
            match_score=recidivism_check['match_score'] if recidivism_check['is_recidivist'] else 100.0,
            match_status='recidivist' if recidivism_check['is_recidivist'] and matched_prisoner.pk != prisoner.pk else 'exact',
            searched_by=captured_by,
            match_details=f"Fingerprint registration - Quality: {quality_score}% - Recidivist: {prisoner.is_recidivist}"
        )
        
        # Create audit log
        FingerprintAuditLog.objects.create(
            prisoner=prisoner,
            operation='capture',
            performed_by=captured_by,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                'quality_score': quality_score,
                'device_id': device_id,
                'device_name': device.name if device else None,
                'is_verified': prisoner.is_identity_verified,
                'is_recidivist': prisoner.is_recidivist,
                'matched_prisoner': matched_prisoner.prisoner_number if recidivism_check['is_recidivist'] else None,
                'match_score': recidivism_check['match_score'] if recidivism_check['is_recidivist'] else None
            },
            success=True
        )
        
        # Update device last used
        if device:
            device.last_used_at = timezone.now()
            device.save()
        
        # Log system activity
        recidivism_note = " - RECIDIVIST DETECTED!" if prisoner.is_recidivist else ""
        ActivityLog.objects.create(
            user=captured_by,
            action='capture_fingerprint',
            model='Prisoner',
            object_id=prisoner.id,
            details=f'Captured fingerprint for prisoner {prisoner.prisoner_number} (Quality: {quality_score}%){recidivism_note}'
        )
        
        logger.info(f"Fingerprint registered for prisoner {prisoner.prisoner_number} - Recidivist: {prisoner.is_recidivist}")
        return prisoner

    @staticmethod
    def search_fingerprint(
        fingerprint_data: str, 
        threshold: float = MATCH_THRESHOLD,
        limit: int = 10,
        include_inactive: bool = True
    ) -> List[Prisoner]:
        """
        Search for prisoners with matching fingerprints.
        
        Args:
            fingerprint_data: The fingerprint template to search for
            threshold: Minimum match threshold (0-100)
            limit: Maximum number of results to return
            include_inactive: Whether to include inactive/released prisoners
        
        Returns:
            List of matching prisoners sorted by match score
        """
        if not fingerprint_data:
            return []
        
        # Get all prisoners with fingerprints
        prisoners = Prisoner.objects.filter(
            fingerprint_template__isnull=False,
            fingerprint_template__gt=''
        )
        
        if not include_inactive:
            prisoners = prisoners.filter(is_active=True)
        
        prisoners = prisoners.select_related('prison_station')
        
        matches = []
        
        for prisoner in prisoners:
            try:
                score, is_match = FingerprintProcessor.match_fingerprints(
                    fingerprint_data, 
                    prisoner.fingerprint_template
                )
                
                if is_match or score >= threshold:
                    matches.append({
                        'prisoner': prisoner,
                        'score': score,
                        'is_match': is_match
                    })
            except Exception as e:
                logger.error(
                    f"Error matching fingerprint for prisoner {prisoner.id}: {str(e)}"
                )
                continue
        
        # Sort by score descending
        matches.sort(key=lambda x: x['score'], reverse=True)
        
        # Return only the top matches
        return [match['prisoner'] for match in matches[:limit]]

    @staticmethod
    def identify_prisoner(
        fingerprint_data: str, 
        threshold: float = MATCH_THRESHOLD,
        station_filter: Optional[PrisonStation] = None
    ) -> Optional[Prisoner]:
        """
        Identify a prisoner by fingerprint.
        
        Args:
            fingerprint_data: The fingerprint template to search for
            threshold: Minimum match threshold (0-100)
            station_filter: Optional prison station to filter results
        
        Returns:
            Matching prisoner if found, None otherwise
        """
        matches = BiometricService.search_fingerprint(fingerprint_data, threshold, limit=5)
        
        if not matches:
            return None
        
        # If station filter is provided, prefer matches from that station
        if station_filter:
            station_matches = [p for p in matches if p.prison_station == station_filter]
            if station_matches:
                return station_matches[0]
        
        return matches[0] if matches else None

    @staticmethod
    def verify_identity(
        prisoner: Prisoner, 
        fingerprint_data: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[bool, float]:
        """
        Verify a prisoner's identity against their registered fingerprint.
        
        Args:
            prisoner: The prisoner to verify
            fingerprint_data: The fingerprint template to verify against
            ip_address: Optional IP address of the request
            user_agent: Optional user agent string
        
        Returns:
            Tuple containing:
            - is_verified: Boolean indicating if identity was verified
            - match_score: Match score (0-100)
        """
        if not prisoner or not prisoner.has_fingerprint:
            return False, 0.0
        
        if not fingerprint_data:
            return False, 0.0
        
        try:
            score, is_match = FingerprintProcessor.match_fingerprints(
                fingerprint_data,
                prisoner.fingerprint_template
            )
            
            # Log the verification attempt
            FingerprintMatch.objects.create(
                searched_prisoner=prisoner,
                matched_prisoner=prisoner if is_match else None,
                match_score=score,
                match_status='exact' if is_match else (
                    'probable' if score >= 50 else 'no_match'
                ),
                searched_by=None,
                match_details=f"Identity verification - Score: {score:.1f}%"
            )
            
            # Create audit log
            FingerprintAuditLog.objects.create(
                prisoner=prisoner,
                operation='verify',
                performed_by=prisoner.fingerprint_captured_by,
                ip_address=ip_address,
                user_agent=user_agent,
                details={
                    'match_score': score,
                    'is_verified': is_match,
                    'threshold': BiometricService.MATCH_THRESHOLD
                },
                success=is_match
            )
            
            return is_match, score
            
        except Exception as e:
            logger.error(f"Identity verification failed for prisoner {prisoner.id}: {str(e)}")
            return False, 0.0

    @staticmethod
    def link_identities(
        prisoner1: Prisoner, 
        prisoner2: Prisoner, 
        verified_by: User, 
        confidence: float
    ) -> bool:
        """
        Link two prisoner identities as the same person.
        
        Args:
            prisoner1: First prisoner
            prisoner2: Second prisoner
            verified_by: User performing the verification
            confidence: Confidence level (0-100)
        
        Returns:
            Boolean indicating if the link was successful
        """
        if prisoner1.pk == prisoner2.pk:
            return False
        
        if confidence < 80.0:
            return False
        
        with transaction.atomic():
            prisoner1.previous_identities.add(prisoner2)
            prisoner2.previous_identities.add(prisoner1)
            
            prisoner1.is_identity_verified = True
            prisoner1.identity_verified_at = timezone.now()
            prisoner1.identity_verified_by = verified_by
            prisoner1.identity_verification_notes = (
                f"Identity linked to {prisoner2.prisoner_number} on {timezone.now().date()}"
            )
            
            prisoner2.is_identity_verified = True
            prisoner2.identity_verified_at = timezone.now()
            prisoner2.identity_verified_by = verified_by
            prisoner2.identity_verification_notes = (
                f"Identity linked to {prisoner1.prisoner_number} on {timezone.now().date()}"
            )
            
            prisoner1.save()
            prisoner2.save()
            
            for prisoner in [prisoner1, prisoner2]:
                FingerprintAuditLog.objects.create(
                    prisoner=prisoner,
                    operation='link',
                    performed_by=verified_by,
                    details={
                        'linked_to': prisoner2.prisoner_number if prisoner == prisoner1 else prisoner1.prisoner_number,
                        'confidence': confidence
                    },
                    success=True
                )
        
        logger.info(f"Linked identities: {prisoner1.prisoner_number} ↔ {prisoner2.prisoner_number}")
        return True

    @staticmethod
    def get_fingerprint_history(prisoner: Prisoner) -> List[FingerprintMatch]:
        """
        Get fingerprint match history for a prisoner.
        
        Args:
            prisoner: The prisoner to get history for
        
        Returns:
            List of fingerprint matches ordered by timestamp
        """
        return FingerprintMatch.objects.filter(
            Q(searched_prisoner=prisoner) | Q(matched_prisoner=prisoner)
        ).order_by('-search_timestamp')


class FingerprintDeviceManager:
    """
    Manages fingerprint scanner devices.
    """
    
    @staticmethod
    def get_available_devices(
        prison_station: Optional[PrisonStation] = None
    ) -> List[FingerprintDevice]:
        """
        Get available fingerprint devices for a prison station.
        
        Args:
            prison_station: Optional prison station filter
        
        Returns:
            List of active fingerprint devices
        """
        queryset = FingerprintDevice.objects.filter(status='active')
        if prison_station:
            queryset = queryset.filter(prison_station=prison_station)
        return list(queryset)

    @staticmethod
    def get_lenovo_integrated_device(
        prison_station: Optional[PrisonStation] = None
    ) -> Optional[FingerprintDevice]:
        """
        Get or create the Lenovo integrated fingerprint device.
        
        Args:
            prison_station: Optional prison station for device assignment
        
        Returns:
            FingerprintDevice instance or None
        """
        queryset = FingerprintDevice.objects.filter(
            device_type='integrated',
            name__icontains='Lenovo'
        )
        if prison_station:
            queryset = queryset.filter(prison_station=prison_station)
        
        device = queryset.first()
        
        if not device and prison_station:
            # Create the device if it doesn't exist
            device = FingerprintDevice.objects.create(
                name='Lenovo Integrated Fingerprint Scanner',
                device_type='integrated',
                serial_number=f'LENOVO-INT-{prison_station.code}',
                status='active',
                prison_station=prison_station,
                notes='Integrated fingerprint scanner on Lenovo laptop'
            )
        
        return device

    @staticmethod
    def get_device_stats(device: FingerprintDevice) -> Dict:
        """
        Get usage statistics for a device.
        
        Args:
            device: The fingerprint device
        
        Returns:
            Dictionary containing device statistics
        """
        return {
            'total_captures': FingerprintAuditLog.objects.filter(
                details__contains=f'"device_name": "{device.name}"'
            ).count(),
            'last_used': device.last_used_at,
            'status': device.status,
            'prison_station': device.prison_station.name if device.prison_station else None
        }