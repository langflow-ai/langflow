"use strict";

/**
 * Rehype plugin that does two things to markdown tables:
 *
 * 1. Inserts U+200B (zero-width space) after every underscore inside <code>
 *    elements in <td> cells, so env-var names like LANGFLOW_CONFIG_DIR wrap
 *    at underscore boundaries without breaking the inline-code styling.
 *
 * 2. Detects columns whose header text matches CENTER_COLUMNS and adds the
 *    CSS class "col-center" to every <th>/<td> in those columns, so Format
 *    and Default are always centered regardless of their column position.
 */

const CENTER_COLUMNS = ["format", "default"];

function walk(node, visitor) {
  visitor(node);
  if (node.children) {
    node.children.forEach((child) => walk(child, visitor));
  }
}

function textContent(node) {
  let text = "";
  walk(node, (n) => {
    if (n.type === "text") text += n.value;
  });
  return text.trim().toLowerCase();
}

function addClass(node, cls) {
  const p = node.properties || (node.properties = {});
  const existing = Array.isArray(p.className) ? p.className : p.className ? [p.className] : [];
  if (!existing.includes(cls)) p.className = [...existing, cls];
}

function processTable(table) {
  // Find thead > tr > th to determine which column indices to center
  const thead = table.children.find((n) => n.type === "element" && n.tagName === "thead");
  if (!thead) return;
  const headerRow = thead.children.find((n) => n.type === "element" && n.tagName === "tr");
  if (!headerRow) return;

  const ths = headerRow.children.filter((n) => n.type === "element" && n.tagName === "th");
  const centerIndices = new Set();
  ths.forEach((th, i) => {
    if (CENTER_COLUMNS.includes(textContent(th))) centerIndices.add(i);
  });

  if (centerIndices.size === 0) return;

  // Add col-center class to matching th and td cells
  [thead, ...table.children.filter((n) => n.type === "element" && n.tagName === "tbody")].forEach(
    (section) => {
      walk(section, (row) => {
        if (row.type !== "element" || row.tagName !== "tr") return;
        const cells = row.children.filter(
          (n) => n.type === "element" && (n.tagName === "td" || n.tagName === "th")
        );
        cells.forEach((cell, i) => {
          if (centerIndices.has(i)) addClass(cell, "col-center");
        });
      });
    }
  );
}

/** @returns {import('unified').Transformer} */
function rehypeTableEnhancements() {
  return (tree) => {
    walk(tree, (node) => {
      if (node.type !== "element") return;

      // 1. Zero-width space after underscores in td > code
      if (node.tagName === "td") {
        walk(node, (inner) => {
          if (inner.type !== "element" || inner.tagName !== "code") return;
          for (const child of inner.children) {
            if (child.type !== "text" || !child.value.includes("_")) continue;
            child.value = child.value.replace(/_/g, "_​");
          }
        });
      }

      // 2. Center columns by header name
      if (node.tagName === "table") {
        processTable(node);
      }
    });
  };
}

module.exports = rehypeTableEnhancements;
