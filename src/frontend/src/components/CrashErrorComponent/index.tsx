export default function CrashErrorComponent({ error, resetErrorBoundary }) {
  return (
    <div className="fixed left-0 top-0 z-50 flex h-full w-full items-center justify-center bg-gray-800 bg-opacity-50">
      <div className="flex h-1/3 min-h-fit max-w-4xl flex-col justify-evenly rounded-lg bg-white p-8 text-start shadow-lg">
        <h1 className="mb-4 text-3xl text-red-500">
          Oops! An unknown error has occurred.
        </h1>
        <p className="mb-4 text-xl text-gray-700">
          Please click the 'Reset Application' button to restore the
          application's state. If the error persists, please create an issue on
          our GitHub page. We apologize for any inconvenience this may have
          caused.
        </p>
        <div className="flex justify-center">
          <button
            onClick={resetErrorBoundary}
            className="mr-4 rounded bg-blue-500 px-4 py-2 font-bold text-white hover:bg-blue-700"
          >
            Reset Application
          </button>
          <a
            href="https://github.com/logspace-ai/langflow/issues/new"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded bg-red-500 px-4 py-2 font-bold text-white hover:bg-red-700"
          >
            Create Issue
          </a>
        </div>
      </div>
    </div>
  );
}
