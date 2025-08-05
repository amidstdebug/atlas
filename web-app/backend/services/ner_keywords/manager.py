import os
import logging
from typing import List, Set, Optional
from .encryption import NERKeywordEncryption

logger = logging.getLogger(__name__)

class NERKeywordManager:
    """Manages NER keywords with encryption and in-memory state"""
    
    def __init__(self):
        self._user_keywords: Set[str] = set()
        self._default_keywords: Set[str] = set()
        self._encryption: Optional[NERKeywordEncryption] = None
        self._is_initialized = False
        self._encrypted_file_path = "ner_keywords_encrypted.txt"
        
        # Load default keywords on initialization
        self._load_default_keywords()
    
    def initialize_encryption(self, password: str) -> bool:
        """Initialize encryption with user-provided password"""
        try:
            self._encryption = NERKeywordEncryption(password)
            
            # Load existing encrypted keywords if they exist
            if os.path.exists(self._encrypted_file_path):
                encrypted_keywords = self._encryption.load_encrypted_keywords(self._encrypted_file_path)
                self._user_keywords = set(encrypted_keywords)
                logger.info(f"Loaded {len(encrypted_keywords)} encrypted user keywords")
            
            self._is_initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            return False
    
    def _load_default_keywords(self):
        """Load default keywords from ner_keywords.txt"""
        try:
            keywords_file = "ner_keywords.txt"
            if os.path.exists(keywords_file):
                with open(keywords_file, 'r') as f:
                    keywords = [
                        line.strip() 
                        for line in f 
                        if line.strip() and not line.strip().startswith('#')
                    ]
                self._default_keywords = set(keywords)
                logger.info(f"Loaded {len(keywords)} default keywords")
            else:
                logger.warning("Default keywords file not found")
        except Exception as e:
            logger.error(f"Failed to load default keywords: {e}")
    
    def add_user_keywords(self, keywords: List[str], password: str) -> bool:
        """Add user keywords and save them encrypted"""
        if not self._is_initialized:
            if not self.initialize_encryption(password):
                return False
        
        try:
            # Add new keywords to the set (removes duplicates automatically)
            new_keywords = [kw.strip() for kw in keywords if kw.strip()]
            self._user_keywords.update(new_keywords)
            
            # Save encrypted keywords
            user_keywords_list = list(self._user_keywords)
            success = self._encryption.save_encrypted_keywords(
                user_keywords_list, 
                self._encrypted_file_path
            )
            
            if success:
                logger.info(f"Added {len(new_keywords)} user keywords, total: {len(self._user_keywords)}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to add user keywords: {e}")
            return False
    
    def remove_user_keywords(self, keywords: List[str]) -> bool:
        """Remove user keywords and update encrypted file"""
        if not self._is_initialized or not self._encryption:
            return False
        
        try:
            keywords_to_remove = set(kw.strip() for kw in keywords if kw.strip())
            self._user_keywords -= keywords_to_remove
            
            # Save updated keywords
            user_keywords_list = list(self._user_keywords)
            success = self._encryption.save_encrypted_keywords(
                user_keywords_list, 
                self._encrypted_file_path
            )
            
            if success:
                logger.info(f"Removed {len(keywords_to_remove)} keywords, remaining: {len(self._user_keywords)}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to remove user keywords: {e}")
            return False
    
    def get_all_keywords(self) -> List[str]:
        """Get all keywords (default + user)"""
        all_keywords = self._default_keywords | self._user_keywords
        return list(all_keywords)
    
    def get_user_keywords(self) -> List[str]:
        """Get only user-defined keywords"""
        return list(self._user_keywords)
    
    def get_default_keywords(self) -> List[str]:
        """Get only default keywords"""
        return list(self._default_keywords)
    
    def clear_user_keywords(self) -> bool:
        """Clear all user keywords"""
        if not self._is_initialized or not self._encryption:
            return False
        
        try:
            self._user_keywords.clear()
            
            # Remove encrypted file
            if os.path.exists(self._encrypted_file_path):
                os.remove(self._encrypted_file_path)
            
            logger.info("Cleared all user keywords")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear user keywords: {e}")
            return False
    
    def is_encryption_initialized(self) -> bool:
        """Check if encryption is initialized"""
        return self._is_initialized
    
    def get_stats(self) -> dict:
        """Get keyword statistics"""
        return {
            "default_keywords_count": len(self._default_keywords),
            "user_keywords_count": len(self._user_keywords),
            "total_keywords_count": len(self._default_keywords | self._user_keywords),
            "encryption_initialized": self._is_initialized
        }

# Global instance
ner_keyword_manager = NERKeywordManager() 