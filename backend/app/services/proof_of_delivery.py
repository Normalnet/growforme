"""
Proof of Delivery Service
Handles digital signatures, photo evidence, and SMS alerts for delivery confirmations.
"""

import os
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, List
from pathlib import Path
import base64
from app.models import (
    db, ProofOfDelivery, Delivery, Order, Farmer, DeliveryStatus
)

logger = logging.getLogger(__name__)

class ProofOfDeliveryService:
    """
    Service for managing Proof of Delivery (PoD) operations.
    Captures signatures, photos, and sends automated alerts.
    """
    
    def __init__(self, upload_folder: str = 'uploads/pod', twilio_client=None):
        """
        Initialize PoD service.
        
        Args:
            upload_folder: Folder to store PoD files
            twilio_client: Twilio SMS client
        """
        self.upload_folder = upload_folder
        self.twilio_client = twilio_client
        
        # Ensure upload folder exists
        Path(upload_folder).mkdir(parents=True, exist_ok=True)
    
    def create_proof_of_delivery(self, delivery_id: str, pod_data: Dict) -> Optional[str]:
        """
        Create a proof of delivery record with signature and photos.
        
        Args:
            delivery_id: Delivery ID
            pod_data: Dictionary containing PoD information
        
        Returns:
            PoD ID if successful, None otherwise
        """
        try:
            delivery = Delivery.query.get(delivery_id)
            if not delivery:
                logger.error(f"Delivery {delivery_id} not found")
                return None
            
            # Extract data
            farmer_name = pod_data.get('farmer_name')
            farmer_phone = pod_data.get('farmer_phone')
            delivery_condition = pod_data.get('delivery_condition')
            notes = pod_data.get('notes')
            location_lat = pod_data.get('location_latitude')
            location_lon = pod_data.get('location_longitude')
            accuracy = pod_data.get('accuracy_meters')
            device_id = pod_data.get('device_id')
            signature_base64 = pod_data.get('signature_data')
            photos_base64 = pod_data.get('photos', [])
            items_verified = pod_data.get('items_verified')
            
            # Save signature if provided
            signature_path = None
            if signature_base64:
                signature_path = self._save_signature(
                    delivery_id, farmer_name, signature_base64
                )
            
            # Save photos if provided
            photo_paths = []
            if photos_base64:
                photo_paths = self._save_photos(
                    delivery_id, farmer_name, photos_base64
                )
            
            # Create PoD record
            pod = ProofOfDelivery(
                delivery_id=delivery_id,
                farmer_name=farmer_name,
                farmer_phone=farmer_phone,
                signature_stored_path=signature_path,
                photo_evidence=photo_paths,
                delivery_condition=delivery_condition,
                notes=notes,
                location_latitude=location_lat,
                location_longitude=location_lon,
                accuracy_meters=accuracy,
                device_id=device_id,
                items_verified=items_verified
            )
            
            db.session.add(pod)
            
            # Update delivery status
            delivery.status = DeliveryStatus.COMPLETED
            delivery.delivery_date = datetime.utcnow()
            delivery.delivery_latitude = location_lat
            delivery.delivery_longitude = location_lon
            
            db.session.commit()
            
            logger.info(f"Created PoD {pod.id} for delivery {delivery_id}")
            
            # Send SMS alert to farmer
            self._send_sms_alert(delivery, pod)
            
            return pod.id
        
        except Exception as e:
            logger.error(f"Error creating PoD for delivery {delivery_id}: {str(e)}")
            db.session.rollback()
            return None
    
    def _save_signature(self, delivery_id: str, farmer_name: str, 
                       signature_base64: str) -> Optional[str]:
        """
        Save signature image to file system.
        
        Args:
            delivery_id: Delivery ID
            farmer_name: Farmer name for file naming
            signature_base64: Base64 encoded signature image
        
        Returns:
            Path to saved signature file
        """
        try:
            # Remove data URI prefix if present
            if ',' in signature_base64:
                signature_base64 = signature_base64.split(',')[1]
            
            # Decode base64
            signature_data = base64.b64decode(signature_base64)
            
            # Generate filename
            signature_id = str(uuid.uuid4())
            filename = f"signature_{delivery_id}_{signature_id}.png"
            filepath = os.path.join(self.upload_folder, filename)
            
            # Save file
            with open(filepath, 'wb') as f:
                f.write(signature_data)
            
            logger.info(f"Saved signature to {filepath}")
            return filepath
        
        except Exception as e:
            logger.error(f"Error saving signature: {str(e)}")
            return None
    
    def _save_photos(self, delivery_id: str, farmer_name: str, 
                    photos_base64: List[str]) -> List[str]:
        """
        Save photo evidence images to file system.
        
        Args:
            delivery_id: Delivery ID
            farmer_name: Farmer name for file naming
            photos_base64: List of base64 encoded photos
        
        Returns:
            List of paths to saved photo files
        """
        saved_paths = []
        
        for idx, photo_base64 in enumerate(photos_base64):
            try:
                # Remove data URI prefix if present
                if ',' in photo_base64:
                    photo_base64 = photo_base64.split(',')[1]
                
                # Decode base64
                photo_data = base64.b64decode(photo_base64)
                
                # Generate filename
                photo_id = str(uuid.uuid4())
                filename = f"photo_{delivery_id}_{idx}_{photo_id}.jpg"
                filepath = os.path.join(self.upload_folder, filename)
                
                # Save file
                with open(filepath, 'wb') as f:
                    f.write(photo_data)
                
                saved_paths.append(filepath)
                logger.info(f"Saved photo {idx} to {filepath}")
            
            except Exception as e:
                logger.error(f"Error saving photo {idx}: {str(e)}")
                continue
        
        return saved_paths
    
    def _send_sms_alert(self, delivery: Delivery, pod: ProofOfDelivery) -> bool:
        """
        Send SMS alert to farmer confirming delivery.
        
        Args:
            delivery: Delivery object
            pod: Proof of Delivery object
        
        Returns:
            True if SMS sent successfully
        """
        if not self.twilio_client:
            logger.warning("Twilio client not configured, skipping SMS")
            return False
        
        try:
            farmer = Farmer.query.get(delivery.order.farmer_id)
            if not farmer:
                logger.error(f"Farmer not found for order {delivery.order_id}")
                return False
            
            # Construct SMS message
            message_body = (
                f"Hello {farmer.name}, your input delivery has been confirmed! "
                f"Delivery condition: {pod.delivery_condition}. "
                f"Thank you for using SmartTechBuddy. Reference: {delivery.delivery_number}"
            )
            
            # Send SMS via Twilio
            message = self.twilio_client.messages.create(
                body=message_body,
                from_='',  # Populate from config
                to=farmer.phone_number
            )
            
            # Update PoD record
            pod.sms_alert_sent = True
            pod.sms_sent_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"SMS sent to {farmer.phone_number}, SID: {message.sid}")
            return True
        
        except Exception as e:
            logger.error(f"Error sending SMS alert: {str(e)}")
            return False
    
    def verify_pod(self, pod_id: str, verified_by: str) -> Optional[Dict]:
        """
        Verify and approve a proof of delivery.
        
        Args:
            pod_id: PoD ID
            verified_by: User ID who is verifying
        
        Returns:
            Verification result
        """
        try:
            pod = ProofOfDelivery.query.get(pod_id)
            if not pod:
                return None
            
            pod.verified = True
            pod.verified_by = verified_by
            pod.verified_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"PoD {pod_id} verified by {verified_by}")
            
            return {
                'pod_id': pod_id,
                'verified': True,
                'verified_at': pod.verified_at.isoformat(),
                'verified_by': verified_by
            }
        
        except Exception as e:
            logger.error(f"Error verifying PoD {pod_id}: {str(e)}")
            return None
    
    def get_delivery_pod(self, delivery_id: str) -> Optional[Dict]:
        """
        Retrieve proof of delivery for a delivery.
        
        Args:
            delivery_id: Delivery ID
        
        Returns:
            PoD data dictionary
        """
        pod = ProofOfDelivery.query.filter_by(delivery_id=delivery_id).first()
        
        if not pod:
            return None
        
        return {
            'id': pod.id,
            'delivery_id': pod.delivery_id,
            'farmer_name': pod.farmer_name,
            'farmer_phone': pod.farmer_phone,
            'delivery_condition': pod.delivery_condition,
            'notes': pod.notes,
            'location': {
                'latitude': pod.location_latitude,
                'longitude': pod.location_longitude,
                'accuracy_meters': pod.accuracy_meters
            },
            'signature_path': pod.signature_stored_path,
            'photo_paths': pod.photo_evidence,
            'items_verified': pod.items_verified,
            'verified': pod.verified,
            'sms_alert_sent': pod.sms_alert_sent,
            'captured_at': pod.captured_at.isoformat() if pod.captured_at else None
        }
