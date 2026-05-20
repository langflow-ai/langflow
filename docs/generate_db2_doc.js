const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, HeadingLevel, BorderStyle, WidthType, ShadingType,
  VerticalAlign, PageBreak
} = require('docx');
const fs = require('fs');

// Color palette
const COLORS = {
  ibmBlue: '0F62FE',
  ibmDark: '001141',
  accent1: '6929C4',   // purple
  accent2: '1192E8',   // light blue
  accent3: '009D9A',   // teal
  accent4: 'FA4D56',   // red
  accent5: 'FF832B',   // orange
  lightBg: 'EDF5FF',
  lightPurple: 'F6F2FF',
  lightTeal: 'D9FBFB',
  lightRed: 'FFF1F1',
  white: 'FFFFFF',
  darkText: '161616',
  midGray: '6F6F6F',
  lightGray: 'F4F4F4',
  borderGray: 'E0E0E0',
};

const border = { style: BorderStyle.SINGLE, size: 1, color: COLORS.borderGray };
const borders = { top: border, bottom: border, left: border, right: border };
const noBorder = { style: BorderStyle.NONE, size: 0, color: COLORS.white };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

function heading1(text, color = COLORS.ibmDark) {
  return new Paragraph({
    spacing: { before: 320, after: 160 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: color, space: 4 } },
    children: [new TextRun({ text, bold: true, size: 36, color, font: 'Arial' })]
  });
}

function heading2(text, color = COLORS.ibmBlue) {
  return new Paragraph({
    spacing: { before: 240, after: 120 },
    children: [new TextRun({ text, bold: true, size: 26, color, font: 'Arial' })]
  });
}

function heading3(text, color = COLORS.ibmDark) {
  return new Paragraph({
    spacing: { before: 180, after: 80 },
    children: [new TextRun({ text, bold: true, size: 22, color, font: 'Arial' })]
  });
}

function body(text, color = COLORS.darkText) {
  return new Paragraph({
    spacing: { after: 120 },
    children: [new TextRun({ text, size: 20, color, font: 'Arial' })]
  });
}

function bullet(text, color = COLORS.darkText, dotColor = COLORS.ibmBlue) {
  return new Paragraph({
    spacing: { after: 80 },
    indent: { left: 480, hanging: 240 },
    children: [
      new TextRun({ text: '▶  ', size: 18, color: dotColor, font: 'Arial' }),
      new TextRun({ text, size: 20, color, font: 'Arial' })
    ]
  });
}

function checkBullet(text, color = COLORS.darkText) {
  return new Paragraph({
    spacing: { after: 80 },
    indent: { left: 480, hanging: 240 },
    children: [
      new TextRun({ text: '✅  ', size: 18, font: 'Arial' }),
      new TextRun({ text, size: 20, color, font: 'Arial' })
    ]
  });
}

function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

function spacer(size = 160) {
  return new Paragraph({ spacing: { after: size }, children: [new TextRun('')] });
}

function twoColTable(col1Items, col2Items, bg1, bg2) {
  const maxRows = Math.max(col1Items.length, col2Items.length);
  const rows = [];
  for (let i = 0; i < maxRows; i++) {
    rows.push(new TableRow({
      children: [
        new TableCell({
          borders: noBorders,
          shading: { fill: bg1, type: ShadingType.CLEAR },
          margins: { top: 60, bottom: 60, left: 180, right: 120 },
          width: { size: 4620, type: WidthType.DXA },
          children: [new Paragraph({
            children: col1Items[i]
              ? [new TextRun({ text: '✓  ', size: 19, color: COLORS.accent3, font: 'Arial' }),
                 new TextRun({ text: col1Items[i], size: 19, color: COLORS.darkText, font: 'Arial' })]
              : [new TextRun('')]
          })]
        }),
        new TableCell({
          borders: noBorders,
          shading: { fill: bg2, type: ShadingType.CLEAR },
          margins: { top: 60, bottom: 60, left: 180, right: 120 },
          width: { size: 4740, type: WidthType.DXA },
          children: [new Paragraph({
            children: col2Items[i]
              ? [new TextRun({ text: '✓  ', size: 19, color: COLORS.accent3, font: 'Arial' }),
                 new TextRun({ text: col2Items[i], size: 19, color: COLORS.darkText, font: 'Arial' })]
              : [new TextRun('')]
          })]
        })
      ]
    }));
  }
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [4620, 4740],
    rows
  });
}

// ─── COVER PAGE ───────────────────────────────────────────────────────────────
const coverPage = [
  // Top blue banner
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [new TableRow({
      children: [new TableCell({
        borders: noBorders,
        shading: { fill: COLORS.ibmDark, type: ShadingType.CLEAR },
        margins: { top: 400, bottom: 400, left: 400, right: 400 },
        children: [
          new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [new TextRun({ text: 'IBM DB2', bold: true, size: 64, color: COLORS.white, font: 'Arial' })]
          }),
          new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [new TextRun({ text: 'VECTOR SEARCH INTEGRATION', bold: true, size: 40, color: '6EA6FF', font: 'Arial' })]
          }),
          new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { before: 120 },
            children: [new TextRun({ text: 'for Langflow', size: 28, color: 'A8C8FF', font: 'Arial', italics: true })]
          }),
        ]
      })]
    })]
  }),
  spacer(200),

  // Sub-header row
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [3100, 3100, 3160],
    rows: [new TableRow({
      children: [
        new TableCell({
          borders: noBorders,
          shading: { fill: COLORS.ibmBlue, type: ShadingType.CLEAR },
          margins: { top: 120, bottom: 120, left: 160, right: 160 },
          children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: '🔒  Enterprise Security', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })]
        }),
        new TableCell({
          borders: noBorders,
          shading: { fill: COLORS.accent1, type: ShadingType.CLEAR },
          margins: { top: 120, bottom: 120, left: 160, right: 160 },
          children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: '⚡  High Performance', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })]
        }),
        new TableCell({
          borders: noBorders,
          shading: { fill: COLORS.accent3, type: ShadingType.CLEAR },
          margins: { top: 120, bottom: 120, left: 160, right: 160 },
          children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: '🤖  AI-Ready RAG', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })]
        }),
      ]
    })]
  }),
  spacer(280),

  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: 'Technical Design & Implementation Report', bold: true, size: 30, color: COLORS.ibmDark, font: 'Arial' })]
  }),
  spacer(80),

  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: 'Version 1.0 — May 2026', size: 22, color: COLORS.midGray, font: 'Arial' })]
  }),
  spacer(240),

  // Metadata table
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2600, 6760],
    rows: [
      ['Team', 'Langflow IBM Integration Team'],
      ['Document Type', 'Technical Design Report'],
      ['Audience', 'Engineering, Product, Stakeholders'],
    ].map(([label, value]) => new TableRow({
      children: [
        new TableCell({
          borders, shading: { fill: COLORS.lightBg, type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          width: { size: 2600, type: WidthType.DXA },
          children: [new Paragraph({ children: [new TextRun({ text: label, bold: true, size: 20, color: COLORS.ibmDark, font: 'Arial' })] })]
        }),
        new TableCell({
          borders, shading: { fill: COLORS.white, type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          width: { size: 6760, type: WidthType.DXA },
          children: [new Paragraph({ children: [new TextRun({ text: value, size: 20, color: COLORS.darkText, font: 'Arial' })] })]
        }),
      ]
    }))
  }),
  pageBreak(),
];

// ─── PAGE 2: OVERVIEW + ARCHITECTURE ─────────────────────────────────────────
const page2 = [
  heading1('01  Overview', COLORS.ibmBlue),
  spacer(80),
  body('The IBM DB2 Vector Search integration brings enterprise-grade vector storage and semantic search to Langflow — enabling AI-powered RAG pipelines and similarity search workflows on top of IBM\'s battle-tested database infrastructure.'),
  spacer(100),

  // Use case cards
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [1820, 1820, 1820, 1820, 1880],
    rows: [new TableRow({
      children: [
        { icon: '🔍', label: 'Semantic Search', color: COLORS.ibmBlue },
        { icon: '📚', label: 'RAG Applications', color: COLORS.accent1 },
        { icon: '🏷️', label: 'Doc Classification', color: COLORS.accent3 },
        { icon: '💡', label: 'Recommendations', color: COLORS.accent5 },
        { icon: '🚨', label: 'Anomaly Detection', color: COLORS.accent4 },
      ].map(({ icon, label, color }) => new TableCell({
        borders: noBorders,
        shading: { fill: color, type: ShadingType.CLEAR },
        margins: { top: 140, bottom: 140, left: 80, right: 80 },
        verticalAlign: VerticalAlign.CENTER,
        children: [
          new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: icon, size: 36, font: 'Arial' })] }),
          new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: label, bold: true, size: 18, color: COLORS.white, font: 'Arial' })] }),
        ]
      }))
    })]
  }),
  spacer(200),

  heading1('02  Architecture', COLORS.accent1),
  spacer(80),
  body('The integration follows a clean layered architecture — from the Langflow UI through the backend component layer, security validation, and down to IBM DB2.'),
  spacer(120),

  // Architecture diagram as styled table
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [
      // Layer 1
      new TableRow({ children: [new TableCell({
        borders: noBorders,
        shading: { fill: COLORS.ibmBlue, type: ShadingType.CLEAR },
        margins: { top: 120, bottom: 80, left: 200, right: 200 },
        children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: '⬜  LANGFLOW FRONTEND', bold: true, size: 22, color: COLORS.white, font: 'Arial' })] })]
      })] }),
      new TableRow({ children: [new TableCell({
        borders: noBorders,
        shading: { fill: '1D4ED8', type: ShadingType.CLEAR },
        margins: { top: 60, bottom: 80, left: 200, right: 200 },
        children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'DB2 Vector Store Component   |   DB2 SQL Component   |   Embedding Models', size: 19, color: 'BFD7FF', font: 'Arial' })] })]
      })] }),
      // Arrow
      new TableRow({ children: [new TableCell({
        borders: noBorders, shading: { fill: COLORS.white, type: ShadingType.CLEAR },
        margins: { top: 40, bottom: 0 },
        children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: '▼', size: 24, color: COLORS.ibmBlue, font: 'Arial' })] })]
      })] }),
      // Layer 2
      new TableRow({ children: [new TableCell({
        borders: noBorders,
        shading: { fill: COLORS.accent1, type: ShadingType.CLEAR },
        margins: { top: 120, bottom: 80, left: 200, right: 200 },
        children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: '⬜  LANGFLOW BACKEND (FastAPI)', bold: true, size: 22, color: COLORS.white, font: 'Arial' })] })]
      })] }),
      new TableRow({ children: [new TableCell({
        borders: noBorders,
        shading: { fill: '5B21B6', type: ShadingType.CLEAR },
        margins: { top: 60, bottom: 80, left: 200, right: 200 },
        children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Component Layer  →  DB2VS Core Module  →  Security Validation Layer', size: 19, color: 'DDD6FE', font: 'Arial' })] })]
      })] }),
      // Arrow
      new TableRow({ children: [new TableCell({
        borders: noBorders, shading: { fill: COLORS.white, type: ShadingType.CLEAR },
        margins: { top: 40, bottom: 0 },
        children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: '▼', size: 24, color: COLORS.accent1, font: 'Arial' })] })]
      })] }),
      // Layer 3
      new TableRow({ children: [new TableCell({
        borders: noBorders,
        shading: { fill: COLORS.accent3, type: ShadingType.CLEAR },
        margins: { top: 120, bottom: 80, left: 200, right: 200 },
        children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: '⬜  IBM DB2 DATABASE', bold: true, size: 22, color: COLORS.white, font: 'Arial' })] })]
      })] }),
      new TableRow({ children: [new TableCell({
        borders: noBorders,
        shading: { fill: '0E7490', type: ShadingType.CLEAR },
        margins: { top: 60, bottom: 100, left: 200, right: 200 },
        children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'ID (VARCHAR)   |   TEXT (CLOB)   |   METADATA (JSON CLOB)   |   EMBEDDING (VECTOR)', size: 19, color: 'CFFAFE', font: 'Arial' })] })]
      })] }),
    ]
  }),
  spacer(120),

  // 4 component cards
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2280, 2280, 2280, 2520],
    rows: [new TableRow({
      children: [
        { title: 'DB2 Vector Store', desc: 'High-level Langflow component for vector ops & data ingestion', color: COLORS.lightBg, tc: COLORS.ibmBlue },
        { title: 'DB2VS Core', desc: 'Low-level vector ops, distance calc, embedding management', color: COLORS.lightPurple, tc: COLORS.accent1 },
        { title: 'DB2 SQL Component', desc: 'Secure SQL execution with read-only mode & timeouts', color: COLORS.lightTeal, tc: COLORS.accent3 },
        { title: 'Security Module', desc: 'Input validation, SQL injection prevention, sanitization', color: COLORS.lightRed, tc: COLORS.accent4 },
      ].map(({ title, desc, color, tc }) => new TableCell({
        borders: { top: { style: BorderStyle.SINGLE, size: 6, color: tc }, bottom: border, left: border, right: border },
        shading: { fill: color, type: ShadingType.CLEAR },
        margins: { top: 120, bottom: 120, left: 120, right: 120 },
        children: [
          new Paragraph({ children: [new TextRun({ text: title, bold: true, size: 20, color: tc, font: 'Arial' })] }),
          new Paragraph({ spacing: { before: 60 }, children: [new TextRun({ text: desc, size: 17, color: COLORS.midGray, font: 'Arial' })] }),
        ]
      }))
    })]
  }),
  pageBreak(),
];

// ─── PAGE 3: FEATURES + SECURITY ─────────────────────────────────────────────
const page3 = [
  heading1('03  Features & Capabilities', COLORS.accent3),
  body('Feature-complete with pgvector and other leading vector stores — plus IBM-grade enterprise additions.'),
  spacer(100),

  heading2('Vector Storage & Search', COLORS.ibmBlue),
  twoColTable(
    ['High-dimensional embedding storage', 'Automatic table creation & schema', 'Cosine similarity search', 'Euclidean distance (L2)', 'Dot product similarity', 'Batch operations for performance'],
    ['Similarity search (k-NN)', 'MMR Search — diversity-aware results', 'Filtered metadata search', 'Similarity scores with results', 'Embedding retrieval with results', 'Multi-query & hybrid search patterns']
  , COLORS.lightBg, COLORS.lightPurple),
  spacer(140),

  heading2('Data Ingestion — All Formats Supported', COLORS.accent1),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [1545, 1545, 1545, 1545, 1545, 1635],
    rows: [new TableRow({
      children: [
        { label: 'Langflow Data', color: COLORS.ibmBlue },
        { label: 'LangChain Docs', color: COLORS.accent1 },
        { label: 'Pandas DataFrame', color: COLORS.accent3 },
        { label: 'JSON / Dict', color: COLORS.accent5 },
        { label: 'CSV strings', color: COLORS.accent4 },
        { label: 'Plain Text', color: '6B7280' },
      ].map(({ label, color }) => new TableCell({
        borders: noBorders,
        shading: { fill: color, type: ShadingType.CLEAR },
        margins: { top: 100, bottom: 100, left: 80, right: 80 },
        children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: label, bold: true, size: 19, color: COLORS.white, font: 'Arial' })] })]
      }))
    })]
  }),
  spacer(140),

  heading2('Distance Metrics', COLORS.accent3),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [3120, 3120, 3120],
    rows: [
      new TableRow({
        children: [
          { label: 'Cosine Similarity', sub: 'Best for normalized vectors', color: COLORS.ibmBlue, range: 'Range: [0, 2]' },
          { label: 'Euclidean Distance', sub: 'Ideal for spatial data', color: COLORS.accent1, range: 'Range: [0, ∞)' },
          { label: 'Dot Product', sub: 'Efficient for pre-normalized', color: COLORS.accent3, range: 'Range: (−∞, ∞)' },
        ].map(({ label, sub, color, range }) => new TableCell({
          borders: noBorders,
          shading: { fill: color, type: ShadingType.CLEAR },
          margins: { top: 120, bottom: 120, left: 140, right: 140 },
          children: [
            new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: label, bold: true, size: 21, color: COLORS.white, font: 'Arial' })] }),
            new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: sub, size: 18, color: 'D1D5DB', font: 'Arial' })] }),
            new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: range, size: 17, color: 'F3F4F6', font: 'Arial', italics: true })] }),
          ]
        }))
      })
    ]
  }),
  pageBreak(),
];

// ─── PAGE 4: SECURITY + TESTING ──────────────────────────────────────────────
const page4 = [
  heading1('04  Security Architecture', COLORS.accent4),
  body('Security is built in defense-in-depth — four independent layers ensure no single bypass compromises the system.'),
  spacer(100),

  // 4 security layers
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [360, 8800, 200],
    rows: [
      { num: '1', title: 'Input Validation', items: ['Identifier validation (table names, columns, DB names)', 'Hostname & IP format enforcement', 'Port range validation (1–65535)', 'Database name length limit (128 chars)'], color: COLORS.ibmBlue },
      { num: '2', title: 'SQL Injection Prevention', items: ['Query operation whitelisting', 'Multi-statement detection (semicolons)', 'Comment pattern blocking (-- and /* */)', '200+ dangerous keyword detection'], color: COLORS.accent1 },
      { num: '3', title: 'String Sanitization', items: ['Single quote escaping (SQL standard)', 'Special character handling', 'Identifier quoting with safe wrappers'], color: COLORS.accent3 },
      { num: '4', title: 'Error Message Sanitization', items: ['Sensitive data redaction from errors', 'Generic user-facing messages', 'Safe internal logging only'], color: COLORS.accent5 },
    ].map(({ num, title, items, color }) => new TableRow({
      children: [
        new TableCell({
          borders: noBorders,
          shading: { fill: color, type: ShadingType.CLEAR },
          margins: { top: 120, bottom: 120, left: 120, right: 80 },
          verticalAlign: VerticalAlign.CENTER,
          children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: num, bold: true, size: 30, color: COLORS.white, font: 'Arial' })] })]
        }),
        new TableCell({
          borders: { top: border, bottom: border, right: border, left: noBorder },
          shading: { fill: COLORS.white, type: ShadingType.CLEAR },
          margins: { top: 100, bottom: 100, left: 140, right: 140 },
          children: [
            new Paragraph({ children: [new TextRun({ text: `Layer ${num}: ${title}`, bold: true, size: 21, color, font: 'Arial' })] }),
            ...items.map(item => new Paragraph({ spacing: { after: 40 }, indent: { left: 200 }, children: [new TextRun({ text: '›  ' + item, size: 18, color: COLORS.darkText, font: 'Arial' })] }))
          ]
        }),
        new TableCell({ borders: noBorders, shading: { fill: COLORS.white, type: ShadingType.CLEAR }, children: [new Paragraph({ children: [new TextRun('')] })] }),
      ]
    }))
  }),
  spacer(160),

  heading1('05  Unit Testing Scope', COLORS.accent1),
  spacer(80),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2280, 2280, 2280, 2520],
    rows: [
      new TableRow({
        children: [
          { title: 'Security Tests', items: ['SQL injection attempts', 'Identifier validation', 'Reserved keywords', 'Multi-statement detection', 'Comment injection'], color: COLORS.accent4, bg: COLORS.lightRed },
          { title: 'DB2VS Unit Tests', items: ['Table existence checks', 'Distance function mapping', 'Embedding dimension validation', 'Document add & retrieve', 'MMR & similarity search'], color: COLORS.ibmBlue, bg: COLORS.lightBg },
          { title: 'Component Tests', items: ['Connection param validation', 'Multi-format data ingestion', 'Duplicate detection (MD5)', 'Metadata extraction', 'Error handling paths'], color: COLORS.accent1, bg: COLORS.lightPurple },
          { title: 'Integration Tests', items: ['DB2 connection flow', 'Table creation lifecycle', 'Vector insert + retrieve', 'Filtered search ops', 'Concurrent operations'], color: COLORS.accent3, bg: COLORS.lightTeal },
        ].map(({ title, items, color, bg }) => new TableCell({
          borders: { top: { style: BorderStyle.SINGLE, size: 8, color }, bottom: border, left: border, right: border },
          shading: { fill: bg, type: ShadingType.CLEAR },
          margins: { top: 120, bottom: 120, left: 120, right: 120 },
          children: [
            new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: title, bold: true, size: 20, color, font: 'Arial' })] }),
            ...items.map(item => new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: '✅  ' + item, size: 17, color: COLORS.darkText, font: 'Arial' })] }))
          ]
        }))
      })
    ]
  }),
  spacer(120),

  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [new TableRow({ children: [new TableCell({
      borders: noBorders,
      shading: { fill: COLORS.ibmDark, type: ShadingType.CLEAR },
      margins: { top: 120, bottom: 120, left: 200, right: 200 },
      children: [new Paragraph({ children: [
        new TextRun({ text: 'Coverage Target: ', bold: true, size: 22, color: '6EA6FF', font: 'Arial' }),
        new TextRun({ text: '90%+ unit test coverage on Security Module, DB2VS Core, and both Components.', size: 22, color: COLORS.white, font: 'Arial' }),
      ] })]
    })] })]
  }),
  pageBreak(),
];

// ─── PAGE 5: IMPLEMENTATION + GUIDELINES ─────────────────────────────────────
const page5 = [
  heading1('06  Implementation Approach', COLORS.ibmBlue),
  spacer(80),

  heading2('Data Ingestion Flow', COLORS.accent1),
  spacer(60),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [
      ['User', 'Ingest data (DataFrame / CSV / JSON / Text)', COLORS.ibmBlue],
      ['Component', 'Parse format → Extract text & metadata → Create Documents', COLORS.accent1],
      ['Component', 'Hash-check existing docs → Filter duplicates (MD5)', COLORS.accent1],
      ['Embedding Model', 'Generate vector embeddings', COLORS.accent3],
      ['Security Layer', 'Validate & sanitize all inputs', COLORS.accent4],
      ['IBM DB2', 'INSERT INTO table (id, text, metadata, embedding)', COLORS.ibmDark],
      ['Component', 'Return success count to User', COLORS.accent3],
    ].map(([actor, action, color]) => new TableRow({
      children: [new TableCell({
        borders: noBorders,
        shading: { fill: color === COLORS.ibmBlue ? COLORS.lightBg : color === COLORS.accent4 ? COLORS.lightRed : color === COLORS.accent3 ? COLORS.lightTeal : color === COLORS.ibmDark ? 'F0F0F0' : COLORS.lightPurple, type: ShadingType.CLEAR },
        margins: { top: 70, bottom: 70, left: 180, right: 180 },
        children: [new Paragraph({ children: [
          new TextRun({ text: `[${actor}]  `, bold: true, size: 19, color, font: 'Arial' }),
          new TextRun({ text: action, size: 19, color: COLORS.darkText, font: 'Arial' }),
        ] })]
      })]
    }))
  }),
  spacer(160),

  heading1('07  Platform Guidelines', COLORS.accent5),
  spacer(80),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [4620, 4740],
    rows: [
      new TableRow({
        children: [
          new TableCell({ borders: noBorders, shading: { fill: COLORS.accent5, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 80, left: 160, right: 160 }, children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Component Standards', bold: true, size: 21, color: COLORS.white, font: 'Arial' })] })] }),
          new TableCell({ borders: noBorders, shading: { fill: COLORS.ibmDark, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 80, left: 160, right: 160 }, children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Code Quality Standards', bold: true, size: 21, color: COLORS.white, font: 'Arial' })] })] }),
        ]
      }),
      ...[
        ['display_name, description, icon for every component', 'Full type hints on all public methods'],
        ['required=True for mandatory input fields', 'Docstrings: Args, Returns, Raises'],
        ['advanced=True for optional/config settings', 'Specific exception types (not bare except)'],
        ['User-friendly error messages with context', 'Resource cleanup in finally blocks'],
        ['check_cached_vector_store decorator', 'Minimal logging in loops — batch milestones only'],
        ['Generic vars for config, Credential for passwords', 'SSL/TLS enforced in all connection strings'],
      ].map(([left, right]) => new TableRow({
        children: [
          new TableCell({ borders, shading: { fill: 'FFF7ED', type: ShadingType.CLEAR }, margins: { top: 60, bottom: 60, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: '›  ' + left, size: 18, color: COLORS.darkText, font: 'Arial' })] })] }),
          new TableCell({ borders, shading: { fill: COLORS.lightBg, type: ShadingType.CLEAR }, margins: { top: 60, bottom: 60, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: '›  ' + right, size: 18, color: COLORS.darkText, font: 'Arial' })] })] }),
        ]
      }))
    ]
  }),
  spacer(200),

  // Footer block
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [new TableRow({ children: [new TableCell({
      borders: noBorders,
      shading: { fill: COLORS.ibmDark, type: ShadingType.CLEAR },
      margins: { top: 180, bottom: 180, left: 240, right: 240 },
      children: [
        new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'IBM DB2 Vector Search for Langflow', bold: true, size: 24, color: '6EA6FF', font: 'Arial' })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 80 }, children: [new TextRun({ text: 'Enterprise-Grade AI Infrastructure', size: 22, color: COLORS.white, font: 'Arial' })] }),
      ]
    })] })]
  }),
];

// ─── BUILD DOC ────────────────────────────────────────────────────────────────
const doc = new Document({
  styles: {
    default: {
      document: { run: { font: 'Arial', size: 20, color: COLORS.darkText } }
    }
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 }
      }
    },
    children: [
      ...coverPage,
      ...page2,
      ...page3,
      ...page4,
      ...page5,
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync('IBM_DB2_VectorSearch_Report.docx', buffer);
  console.log('✅ Document created: IBM_DB2_VectorSearch_Report.docx');
  console.log('📄 You can now open it in Word and export to PDF');
}).catch(console.error);

// Made with Bob
