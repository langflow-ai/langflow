import { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";

interface MermaidDiagramProps {
  definition: string;
  className?: string;
}

export const MermaidDiagram = ({ definition, className }: MermaidDiagramProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRendering, setIsRendering] = useState(true);
  const [svgContent, setSvgContent] = useState<string | null>(null);

  useEffect(() => {
    if (!definition) {
      console.log("MermaidDiagram: No definition provided");
      setIsRendering(false);
      return;
    }

    const renderDiagram = async () => {
      try {
        console.log("MermaidDiagram: Starting render with definition:", definition);
        setIsRendering(true);
        setError(null);

        // Initialize mermaid with simple config
        mermaid.initialize({
          startOnLoad: false,
          theme: "default",
          securityLevel: "loose"
        });

        // Generate unique ID for this diagram
        const id = `mermaid-${Math.random().toString(36).substr(2, 9)}`;
        
        // We don't need to clear content since we're using state for SVG
        
        // Render the diagram
        console.log("MermaidDiagram: Calling mermaid.render with id:", id);
        const { svg } = await mermaid.render(id, definition);
        console.log("MermaidDiagram: Render successful, SVG length:", svg?.length);
        
        setSvgContent(svg);
        setIsRendering(false);
      } catch (err) {
        console.error("MermaidDiagram: Rendering error:", err);
        setError(err instanceof Error ? err.message : "Failed to render diagram");
        setIsRendering(false);
      }
    };

    // Add a small delay to ensure DOM is ready
    const timer = setTimeout(() => {
      renderDiagram();
    }, 100);

    return () => clearTimeout(timer);
  }, [definition]);

  if (isRendering) {
    return (
      <div className="flex items-center justify-center p-8 bg-gray-50 dark:bg-gray-900 rounded-md">
        <div className="flex items-center gap-2">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" />
          <span className="text-sm text-gray-600 dark:text-gray-400">Rendering diagram...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
        <div className="flex items-start gap-2">
          <div className="flex-1">
            <p className="text-sm font-medium text-red-800 dark:text-red-200">Failed to render diagram</p>
            <p className="text-xs text-red-600 dark:text-red-400 mt-1">{error}</p>
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

  if (!svgContent) {
    return (
      <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-md">
        <p className="text-sm">No diagram content to display</p>
      </div>
    );
  }


  return (
    <div className={`mermaid-diagram-container ${className || ''}`}>
      <div 
        className="w-full overflow-auto bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 rounded-md p-4"
        style={{ maxHeight: 'min(600px, 50vh)' }}
        ref={containerRef}
        dangerouslySetInnerHTML={{ __html: svgContent }}
      />
      <div className="flex justify-end mt-2 gap-2">
        <button
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            const blob = new Blob([svgContent], { type: "image/svg+xml" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "diagram.svg";
            a.click();
            URL.revokeObjectURL(url);
          }}
          type="button"
          className="text-xs text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800"
        >
          <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Download SVG
        </button>
      </div>
    </div>
  );
};

export default MermaidDiagram;