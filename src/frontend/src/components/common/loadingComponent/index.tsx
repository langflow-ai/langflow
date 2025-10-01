import type { LoadingComponentProps } from "../../../types/components";

const langflowTips = [
  "💡 Connect components by dragging from output to input handles",
  "🔧 Use the playground to test your flows before deploying",
  "📝 Right-click any component to view its documentation",
  "⚡ Press Ctrl+Space for quick component search",
  "🎯 Use environment variables to keep your API keys secure",
  "🔄 Components run automatically when their inputs change",
  "📊 Check the logs panel for debugging information",
  "🚀 Export your flows as API endpoints with one click"
];

export default function LoadingComponent({
  remSize,
}: LoadingComponentProps): JSX.Element {
  const randomTip = langflowTips[Math.floor(Math.random() * langflowTips.length)];
  
  return (
    <div role="status" aria-live="polite" className="flex flex-col items-center justify-center space-y-4">
      <svg
        aria-hidden="true"
        className="fill-primary text-muted"
        style={{ 
          width: `${remSize * 4}px`, 
          height: `${remSize * 4}px`,
          animation: 'spin 2s linear infinite'
        }}
        viewBox="0 0 100 101"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z"
          fill="currentColor"
        />
        <path
          d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z"
          fill="currentFill"
        />
      </svg>
      
      <div className="text-center space-y-3">
        <span className="text-lg text-primary font-medium">Loading</span>
        <p className="text-sm text-muted-foreground max-w-sm px-4">
          {randomTip}
        </p>
      </div>
      
      <style jsx>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
