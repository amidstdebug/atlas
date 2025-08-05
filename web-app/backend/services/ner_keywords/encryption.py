import os
import base64
import json
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class NERKeywordEncryption:
    """Handles encryption and decryption of NER keywords using Fernet (AES 128)"""
    
    def __init__(self, password: str):
        """Initialize encryption with a password-derived key"""
        self.password = password.encode()
        self._key = None
        self._fernet = None
        self._init_encryption()
    
    def _init_encryption(self):
        """Initialize the Fernet encryption object"""
        # Use a fixed salt for consistency (in production, you might want to store this)
        salt = b'ner_keywords_salt_2024_atlas'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        self._key = base64.urlsafe_b64encode(kdf.derive(self.password))
        self._fernet = Fernet(self._key)
    
    def encrypt_keywords(self, keywords: List[str]) -> str:
        """Encrypt a list of keywords and return base64 encoded string"""
        try:
            # Convert keywords list to JSON string
            keywords_json = json.dumps(keywords)
            
            # Encrypt the JSON string
            encrypted_data = self._fernet.encrypt(keywords_json.encode())
            
            # Return base64 encoded encrypted data
            return base64.urlsafe_b64encode(encrypted_data).decode()
            
        except Exception as e:
            logger.error(f"Failed to encrypt keywords: {e}")
            raise
    
    def decrypt_keywords(self, encrypted_data: str) -> List[str]:
        """Decrypt base64 encoded string and return list of keywords"""
        try:
            # Decode base64
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            
            # Decrypt the data
            decrypted_data = self._fernet.decrypt(encrypted_bytes)
            
            # Parse JSON and return keywords list
            keywords = json.loads(decrypted_data.decode())
            
            return keywords if isinstance(keywords, list) else []
            
        except Exception as e:
            logger.error(f"Failed to decrypt keywords: {e}")
            return []
    
    def save_encrypted_keywords(self, keywords: List[str], filepath: str) -> bool:
        """Encrypt and save keywords to file"""
        try:
            encrypted_data = self.encrypt_keywords(keywords)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'w') as f:
                f.write(encrypted_data)
            
            logger.info(f"Encrypted keywords saved to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save encrypted keywords: {e}")
            return False
    
    def load_encrypted_keywords(self, filepath: str) -> List[str]:
        """Load and decrypt keywords from file"""
        try:
            if not os.path.exists(filepath):
                logger.info(f"Encrypted keywords file not found: {filepath}")
                return []
            
            with open(filepath, 'r') as f:
                encrypted_data = f.read().strip()
            
            if not encrypted_data:
                return []
            
            keywords = self.decrypt_keywords(encrypted_data)
            logger.info(f"Loaded {len(keywords)} encrypted keywords from {filepath}")
            return keywords
            
        except Exception as e:
            logger.error(f"Failed to load encrypted keywords: {e}")
            return [] 