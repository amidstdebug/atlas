# NER Keywords Management System

This system provides simple, unencrypted storage for user-defined Named Entity Recognition (NER) keywords in the ATLAS application.

## Features

- **Simple text format**: Use color-coded format like `[red] emergency urgent [yellow] weather visibility`
- **JSON storage**: Keywords are stored in a simple JSON file
- **Live preview**: See parsed keywords organized by color categories
- **Export/Import**: Backup and share keyword configurations
- **Auto-save**: Keywords are automatically saved as you type

## Architecture

### Components

1. **SimpleNERKeywordManager** (`simple_manager.py`)
   - Handles keyword parsing from color-coded text format
   - Manages JSON file storage
   - Provides export/import functionality

2. **API Endpoints** (`api/ner_keywords_simple.py`)
   - `/ner-keywords/data` - Get keywords data and raw text
   - `/ner-keywords/update` - Update keywords from raw text
   - `/ner-keywords/export` - Export keywords as JSON
   - `/ner-keywords/import` - Import keywords from JSON
   - `/ner-keywords/import-file` - Import from uploaded file
   - `/ner-keywords/stats` - Get keyword statistics

3. **Frontend Component** (`components/SimpleNERKeywordManager.vue`)
   - Vue 3 component with textarea for keyword input
   - Live preview of parsed keywords
   - Export/import buttons
   - Statistics display

## Usage

### Text Format

Use square brackets to define color categories, followed by space-separated keywords:

```
[red] emergency urgent critical mayday
[yellow] weather visibility fog rain
[blue] aircraft runway tower control
[green] clearance approved departure
[purple] time minutes hours delay
```

### Available Colors

- `red` (#ef4444)
- `yellow` (#facc15)
- `blue` (#3b82f6)
- `green` (#22c55e)
- `purple` (#a855f7)
- `orange` (#f97316)
- `pink` (#ec4899)
- `gray` (#6b7280)

### Backend Setup

No special setup required. The system automatically:
- Creates `ner_keywords.json` on first use
- Initializes with example keywords
- Handles parsing and storage

### Frontend Usage

1. Navigate to the NER Keywords page
2. Edit keywords in the textarea using the color-coded format
3. Keywords are auto-saved after 1 second of no typing
4. Use Export/Import buttons to backup or share configurations
5. View live preview and statistics below the editor

## File Structure

```
ner_keywords.json - Main storage file containing:
{
  "version": "1.0",
  "categories": { "red": "#ef4444", ... },
  "keywords": { "red": ["emergency", "urgent"], ... },
  "raw_text": "[red] emergency urgent [yellow] weather..."
}
```

## Migration from Old System

The old encrypted system has been completely removed. If you had encrypted keywords:
1. Export them from the old system (if still available)
2. Manually copy keywords to the new text format
3. The new system is much simpler and more user-friendly 