# IBM DB2 Vector Search Documentation Generator

This directory contains a Node.js script to generate a professional Word document for the IBM DB2 Vector Search integration.

## Files

- `generate_db2_doc.js` - Node.js script that generates the Word document
- `IBM_DB2_VECTOR_SEARCH_DOCUMENTATION.md` - Full detailed markdown documentation
- `IBM_DB2_VECTOR_SEARCH_PDF.md` - Concise PDF-ready markdown with Mermaid diagrams

## Generate Word Document

### Prerequisites

```bash
# Install Node.js (if not already installed)
# macOS: brew install node
# Ubuntu: sudo apt install nodejs npm
```

### Generate the Document

```bash
cd docs
npm install docx
node generate_db2_doc.js
```

This will create: **`IBM_DB2_VectorSearch_Report.docx`**

### Convert to PDF

Once the Word document is generated, you can convert it to PDF:

**Option 1: Microsoft Word**
1. Open `IBM_DB2_VectorSearch_Report.docx` in Microsoft Word
2. File → Save As → PDF
3. Save as `IBM_DB2_VectorSearch_Report.pdf`

**Option 2: LibreOffice (Free)**
```bash
# macOS
brew install --cask libreoffice
libreoffice --headless --convert-to pdf IBM_DB2_VectorSearch_Report.docx

# Ubuntu
sudo apt install libreoffice
libreoffice --headless --convert-to pdf IBM_DB2_VectorSearch_Report.docx
```

**Option 3: Online Converter**
- Upload to [CloudConvert](https://cloudconvert.com/docx-to-pdf)
- Or use [Zamzar](https://www.zamzar.com/convert/docx-to-pdf/)

## Document Contents

The generated document includes:

### Page 1: Cover Page
- Professional IBM-branded header
- Feature highlights (Security, Performance, AI-Ready)
- Metadata table

### Page 2: Overview & Architecture
- Use case cards (Semantic Search, RAG, Classification, etc.)
- Layered architecture diagram
- Component descriptions

### Page 3: Features & Security
- Vector storage & search capabilities
- Data ingestion formats
- Distance metrics comparison
- Enterprise features vs pgvector

### Page 4: Security & Testing
- 4-layer defense-in-depth security
- Security features breakdown
- Unit testing scope (90%+ coverage)

### Page 5: Implementation & Guidelines
- Data ingestion flow sequence
- Platform guidelines
- Component & code quality standards

## Styling

The document uses IBM Design Language colors:
- **IBM Blue** (#0F62FE) - Primary brand color
- **IBM Dark** (#001141) - Headers and emphasis
- **Accent Colors** - Purple, Teal, Orange, Red for categorization
- **Professional Layout** - Tables, colored sections, clear hierarchy

## Troubleshooting

### Error: Cannot find module 'docx'
```bash
cd docs
npm install docx
```

### Error: Permission denied
```bash
chmod +x generate_db2_doc.js
```

### Document not generated
Check the terminal output for errors. The script should print:
```
✅ Document created: IBM_DB2_VectorSearch_Report.docx
📄 You can now open it in Word and export to PDF
```

## Customization

To modify the document:

1. Edit `generate_db2_doc.js`
2. Modify colors in the `COLORS` object
3. Update content in the page arrays (`coverPage`, `page2`, etc.)
4. Run the script again to regenerate

## Support

For issues or questions:
- Check the generated markdown files for reference
- Review the component source code in `src/lfx/src/lfx/components/ibm/`
- Consult the security module: `src/lfx/src/lfx/components/ibm/db2_security.py`