export default function CrashErrorComponent({ error, resetErrorBoundary }) {
  return (
    <div className="fixed top-0 left-0 w-full h-full flex items-center justify-center bg-gray-800 bg-opacity-50 z-50">
      <div className="bg-white max-w-4xl h-1/3 min-h-fit rounded-lg shadow-lg p-8 text-start flex flex-col justify-evenly">
        <h1 className="text-red-500 text-3xl mb-4">
          Oops! An unknown error has occurred.
        </h1>
        <p className="text-gray-700 mb-4 text-xl">
          Please click the 'Reset Application' button to restore the
          application's state. If the error persists, please create an issue on
          our GitHub page. We apologize for any inconvenience this may have
          caused.
        </p>
        <div className="flex justify-center">
          <button
            onClick={resetErrorBoundary}
            className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded mr-4"
          >
            Reset Application
          </button>
          <a
            href="https://github.com/logspace-ai/langflow/issues/new"
            target="_blank"
            rel="noopener noreferrer"
            className="bg-red-500 hover:bg-red-700 text-white font-bold py-2 px-4 rounded"
          >
            Create Issue
          </a>
        </div>
      </div>
    </div>
  );
}
