# NER Keywords Encryption System

This system provides secure, encrypted storage for user-defined Named Entity Recognition (NER) keywords in the ATLAS application.

## Features

- **Password-based encryption**: Uses PBKDF2 with SHA-256 for key derivation
- **AES encryption**: Fernet (AES 128) for symmetric encryption
- **In-memory storage**: Keywords are decrypted and stored in memory only during server runtime
- **No persistence**: User keywords are cleared from memory when the server shuts down
- **Secure file storage**: Encrypted keywords are stored in `ner_keywords_encrypted.txt`

## Architecture

### Components

1. **NERKeywordEncryption** (`encryption.py`)
   - Handles encryption/decryption using Fernet
   - PBKDF2 key derivation with 100,000 iterations
   - Base64 encoding for storage

2. **NERKeywordManager** (`manager.py`)
   - Manages in-memory keyword state
   - Loads default keywords from `ner_keywords.txt`
   - Handles user keyword CRUD operations

3. **API Endpoints** (`api/ner_keywords.py`)
   - `/api/ner-keywords/initialize` - Initialize encryption
   - `/api/ner-keywords/add` - Add encrypted keywords
   - `/api/ner-keywords/user` - Get user keywords
   - `/api/ner-keywords/stats` - Get statistics
   - `/api/ner-keywords/clear` - Clear all user keywords

4. **Frontend Component** (`components/NERKeywordManager.vue`)
   - Vue 3 component for keyword management
   - Password input for encryption initialization
   - Keyword addition/removal interface

## Security Features

- **Password-based encryption**: User-provided password secures the keywords
- **Salt-based key derivation**: Fixed salt ensures consistent key generation
- **No password storage**: Passwords are never stored, only used for encryption
- **Runtime-only decryption**: Keywords exist in memory only during server operation

## Usage

### Backend Setup

1. Install dependencies:
```bash
pip install cryptography==44.0.0
```

2. The system automatically loads:
   - Default keywords from `ner_keywords.txt`
   - Encrypted user keywords from `ner_keywords_encrypted.txt` (if exists)

### Frontend Integration

1. Navigate to `/ner-keywords` page
2. Initialize encryption with a secure password (min 6 characters)
3. Add keywords (one per line or comma-separated)
4. Keywords are automatically encrypted and saved

### API Integration

```javascript
// Initialize encryption
await $fetch('/api/ner-keywords/initialize', {
  method: 'POST',
  body: { password: 'your-secure-password' }
})

// Add keywords
await $fetch('/api/ner-keywords/add', {
  method: 'POST', 
  body: {
    keywords: ['keyword1', 'keyword2'],
    password: 'your-secure-password'
  }
})
```

## File Structure

```
services/ner_keywords/
├── __init__.py
├── encryption.py      # Encryption utilities
├── manager.py         # Keyword manager
└── README.md          # This file

api/
└── ner_keywords.py    # API endpoints

ner_keywords.txt              # Default keywords (plaintext)
ner_keywords_encrypted.txt    # User keywords (encrypted)
```

## Security Considerations

1. **Password Strength**: Ensure users choose strong passwords
2. **HTTPS**: Always use HTTPS in production
3. **Key Management**: Consider using environment variables for salt in production
4. **Access Control**: API endpoints require authentication
5. **Memory Management**: Keywords are cleared on server shutdown

## Integration with NER Processing

The system integrates with existing NER processing in `api/summary.py`:

```python
from ..services.ner_keywords.manager import ner_keyword_manager

# Get all keywords (default + user)
keywords = ner_keyword_manager.get_all_keywords()
```

## Troubleshooting

- **Encryption fails**: Check password length (min 6 characters)
- **Keywords not loading**: Verify encryption initialization
- **Permission errors**: Check file write permissions
- **Memory issues**: Keywords are cleared on server restart (expected behavior) 