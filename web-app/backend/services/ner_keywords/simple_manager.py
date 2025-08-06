import os
import json
import logging
import re
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class SimpleNERKeywordManager:
    """Simplified NER keyword manager using environment variables for security"""
    
    def __init__(self):
        # Load environment variables from ner.env if it exists
        self._load_env_file()
        self._keywords_data: Dict[str, Any] = self._get_default_structure()
        self._load_data()
    
    def _load_env_file(self):
        """Load NER-specific environment variables from ner.env file"""
        ner_env_path = os.path.join(os.path.dirname(__file__), '..', '..', 'ner.env')
        if os.path.exists(ner_env_path):
            load_dotenv(ner_env_path)
            logger.info(f"Loaded NER environment variables from {ner_env_path}")
        else:
            logger.info("No ner.env file found, using system environment variables")
    
    def _get_default_structure(self) -> Dict[str, Any]:
        """Get the default data structure"""
        return {
            "version": "1.0",
            "categories": {
                "red": "#ef4444",
                "yellow": "#facc15", 
                "blue": "#3b82f6",
                "green": "#22c55e",
                "purple": "#a855f7",
                "orange": "#f97316",
                "pink": "#ec4899",
                "gray": "#6b7280"
            },
            "keywords": {},  # category -> list of keywords
            "raw_text": ""   # the raw text format for editing
        }
    
    def _load_data(self):
        """Load keywords data from environment variables"""
        try:
            # Get raw text from environment variable
            raw_text = os.getenv('NER_KEYWORDS_RAW_TEXT', '')
            
            if raw_text:
                self._keywords_data["raw_text"] = raw_text
                self._parse_raw_text()
                logger.info("Loaded keywords from environment variables")
            else:
                # Initialize with example if no environment variable is set
                self._keywords_data["raw_text"] = "[red] emergency urgent critical [yellow] weather visibility [blue] aircraft runway [green] clearance approved [purple] time minutes"
                self._parse_raw_text()
                logger.info("Initialized with default keywords (no environment variable found)")
                
        except Exception as e:
            logger.error(f"Failed to load keywords data from environment: {e}")
            self._keywords_data = self._get_default_structure()
    
    def _save_data(self) -> bool:
        """Save keywords data to environment file"""
        try:
            ner_env_path = os.path.join(os.path.dirname(__file__), '..', '..', 'ner.env')
            
            # Read existing environment file if it exists
            existing_env = {}
            if os.path.exists(ner_env_path):
                with open(ner_env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            existing_env[key] = value
            
            # Update the NER keywords raw text
            existing_env['NER_KEYWORDS_RAW_TEXT'] = f'"{self._keywords_data["raw_text"]}"'
            
            # Write back to file
            with open(ner_env_path, 'w', encoding='utf-8') as f:
                f.write("# NER Keywords Environment Variables\n")
                f.write("# This file contains sensitive keyword data - DO NOT commit to version control\n\n")
                
                for key, value in existing_env.items():
                    f.write(f"{key}={value}\n")
            
            # Update current environment
            os.environ['NER_KEYWORDS_RAW_TEXT'] = self._keywords_data["raw_text"]
            
            logger.info(f"Saved keywords to {ner_env_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save keywords data to environment: {e}")
            return False
    
    def _parse_raw_text(self):
        """Parse raw text format like [red] keyword keyword [yellow] keyword keyword"""
        self._keywords_data["keywords"] = {}
        
        if not self._keywords_data.get("raw_text"):
            return
        
        # Pattern to match [color] followed by keywords until next [color] or end
        pattern = r'\[(\w+)\]\s*([^\[]+?)(?=\[|\Z)'
        matches = re.findall(pattern, self._keywords_data["raw_text"], re.IGNORECASE | re.DOTALL)
        
        for color, keywords_text in matches:
            color = color.lower()
            if color in self._keywords_data["categories"]:
                # Split keywords by whitespace and filter empty ones
                keywords = [kw.strip() for kw in keywords_text.split() if kw.strip()]
                if keywords:
                    self._keywords_data["keywords"][color] = keywords
    
    def _generate_raw_text(self):
        """Generate raw text format from keywords data"""
        raw_parts = []
        for color, keywords in self._keywords_data["keywords"].items():
            if keywords:
                keywords_str = " ".join(keywords)
                raw_parts.append(f"[{color}] {keywords_str}")
        
        self._keywords_data["raw_text"] = " ".join(raw_parts)
    
    # Public API methods
    def get_raw_text(self) -> str:
        """Get the raw text format for editing"""
        return self._keywords_data.get("raw_text", "")
    
    def update_from_raw_text(self, raw_text: str) -> bool:
        """Update keywords from raw text format"""
        try:
            self._keywords_data["raw_text"] = raw_text.strip()
            self._parse_raw_text()
            return self._save_data()
        except Exception as e:
            logger.error(f"Failed to update from raw text: {e}")
            return False
    
    def get_categories(self) -> Dict[str, str]:
        """Get available categories with their colors"""
        return self._keywords_data.get("categories", {})
    
    def get_keywords_by_category(self) -> Dict[str, List[str]]:
        """Get keywords organized by category"""
        return self._keywords_data.get("keywords", {})
    
    def get_all_keywords_flat(self) -> List[str]:
        """Get all keywords as a flat list"""
        all_keywords = []
        for keywords in self._keywords_data.get("keywords", {}).values():
            all_keywords.extend(keywords)
        return all_keywords
    

    
    def get_stats(self) -> Dict[str, Any]:
        """Get keyword statistics"""
        keywords_by_cat = self.get_keywords_by_category()
        total_keywords = sum(len(keywords) for keywords in keywords_by_cat.values())
        
        return {
            "total_keywords": total_keywords,
            "categories_used": len(keywords_by_cat),
            "keywords_by_category": {cat: len(keywords) for cat, keywords in keywords_by_cat.items()}
        }
    
    def export_data(self) -> Dict[str, Any]:
        """Export all data for backup/sharing"""
        return self._keywords_data.copy()
    
    def import_data(self, data: Dict[str, Any]) -> bool:
        """Import data from backup/sharing"""
        try:
            # Validate structure
            if "categories" not in data or "raw_text" not in data:
                raise ValueError("Invalid data structure")
            
            self._keywords_data = data
            self._parse_raw_text()
            return self._save_data()
        except Exception as e:
            logger.error(f"Failed to import data: {e}")
            return False

# Global instance
simple_ner_manager = SimpleNERKeywordManager() 