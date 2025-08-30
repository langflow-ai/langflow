import DOMPurify from "dompurify";
import mermaid from "mermaid";
import { useEffect, useRef, useState } from "react";

interface MermaidDiagramProps {
  definition: string;
  className?: string;
}

// Initialize mermaid only once at module level
let mermaidInitialized = false;

export const MermaidDiagram = ({
  definition,
  className,
}: MermaidDiagramProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRendering, setIsRendering] = useState(true);
  const [svgContent, setSvgContent] = useState<string>("");
  const renderIdRef = useRef(0);

  // Initialize mermaid only once
  useEffect(() => {
    if (!mermaidInitialized) {
      const isDark = document.documentElement.classList.contains("dark");
      mermaid.initialize({
        startOnLoad: false,
        theme: isDark ? "dark" : "default",
        securityLevel: "strict",
        flowchart: {
          useMaxWidth: true,
          htmlLabels: true,
          curve: "basis",
        },
        themeVariables: {
          fontSize: "16px",
        },
      });
      mermaidInitialized = true;
      if (import.meta.env.DEV) {
        console.debug("MermaidDiagram: Mermaid initialized");
      }
    }
  }, []);

  useEffect(() => {
    if (!definition) {
      if (import.meta.env.DEV) {
        console.debug("MermaidDiagram: No definition provided");
      }
      setIsRendering(false);
      return;
    }

    const renderDiagram = async () => {
      const currentRenderId = ++renderIdRef.current;

      try {
        if (import.meta.env.DEV) {
          console.debug("MermaidDiagram: Starting render");
        }
        setIsRendering(true);
        setError(null);

        // Generate unique ID for this diagram
        const id = `mermaid-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;

        // Render the diagram
        const { svg, bindFunctions } = await mermaid.render(id, definition);

        // Only update if this is still the current render
        if (currentRenderId === renderIdRef.current && containerRef.current) {
          // Sanitize SVG for security while preserving text content
          const sanitizedSvg = DOMPurify.sanitize(svg, {
            USE_PROFILES: { svg: true, svgFilters: true },
            ADD_TAGS: ["foreignObject"],
            ADD_ATTR: [
              "style",
              "class",
              "id",
              "width",
              "height",
              "viewBox",
              "transform",
            ],
          });

          // Store the sanitized SVG content
          setSvgContent(sanitizedSvg);
          setIsRendering(false);

          // Bind interactive functions after React renders the SVG
          if (bindFunctions && containerRef.current) {
            setTimeout(() => {
              if (containerRef.current) {
                bindFunctions(containerRef.current);
              }
            }, 0);
          }

          if (import.meta.env.DEV) {
            console.debug("MermaidDiagram: Render complete");
          }
        }
      } catch (err) {
        if (currentRenderId === renderIdRef.current) {
          const errorMessage =
            err instanceof Error ? err.message : "Failed to render diagram";
          if (import.meta.env.DEV) {
            console.error("MermaidDiagram: Rendering error:", err);
          }
          setError(errorMessage);
          setIsRendering(false);
        }
      }
    };

    // Call renderDiagram immediately (removed the 100ms delay)
    renderDiagram();
  }, [definition]);

  if (error) {
    return (
      <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
        <div className="flex items-start gap-2">
          <div className="flex-1">
            <p className="text-sm font-medium text-red-800 dark:text-red-200">
              Failed to render diagram
            </p>
            <p className="text-xs text-red-600 dark:text-red-400 mt-1">
              {error}
            </p>
            <details className="mt-2">
              <summary className="text-xs cursor-pointer text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200">
                View source
              </summary>
              <pre className="mt-2 p-2 bg-gray-100 dark:bg-gray-800 rounded text-xs overflow-x-auto">
                <code>{definition}</code>
              </pre>
            </details>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`mermaid-diagram-container w-full ${className || ""}`}>
      <div
        className="w-full overflow-x-auto overflow-y-auto bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 rounded-md p-4"
        style={{
          maxHeight: "min(600px, 50vh)",
          minHeight: "200px",
        }}
        ref={(el) => {
          containerRef.current = el;
          // Safely parse and insert SVG using DOMParser (avoids innerHTML security concerns)
          if (el && svgContent && !isRendering) {
            // Clear existing content
            el.replaceChildren();
            
            // Parse the sanitized SVG using DOMParser
            const parser = new DOMParser();
            const doc = parser.parseFromString(svgContent, "image/svg+xml");
            const svgElement = doc.documentElement;
            
            // Check for parsing errors
            if (svgElement.nodeName === "parsererror") {
              console.error("Failed to parse SVG content");
              return;
            }
            
            // Import and append the SVG node
            const importedSvg = el.ownerDocument.importNode(svgElement, true);
            el.appendChild(importedSvg);
            
            // Apply styling to the SVG element
            if (importedSvg.nodeName.toLowerCase() === "svg") {
              const svg = importedSvg as SVGElement;
              // Set SVG to scale properly
              svg.style.maxWidth = "100%";
              svg.style.height = "auto";
              svg.style.display = "block";
              svg.style.margin = "0 auto";
              // Remove any hardcoded dimensions
              svg.removeAttribute("width");
              svg.removeAttribute("height");
              // Let viewBox handle the sizing
              if (
                !svg.hasAttribute("viewBox") &&
                svg.hasAttribute("width") &&
                svg.hasAttribute("height")
              ) {
                const width = svg.getAttribute("width");
                const height = svg.getAttribute("height");
                svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
              }
            }
          }
        }}
      >
        {isRendering && (
          <div className="flex items-center justify-center py-8">
            <div className="flex items-center gap-2">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Rendering diagram...
              </span>
            </div>
          </div>
        )}
      </div>
      <div className="flex justify-end mt-2 gap-2">
        <button
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            if (svgContent) {
              const blob = new Blob([svgContent], { type: "image/svg+xml" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `diagram-${Date.now()}.svg`;
              a.click();
              URL.revokeObjectURL(url);
            }
          }}
          type="button"
          aria-label="Download diagram as SVG"
          className="text-xs text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800"
        >
          <svg
            className="h-3 w-3"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
            />
          </svg>
          Download SVG
        </button>
      </div>
    </div>
  );
};

export default MermaidDiagram;
