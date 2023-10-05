import { crashComponentPropsType } from "../../types/components";

export default function CrashErrorComponent({
  error,
  resetErrorBoundary,
}: crashComponentPropsType): JSX.Element {
  return (
    <div className="fixed left-0 top-0 z-50 flex h-full w-full items-center justify-center bg-foreground bg-opacity-50">
      <div className="flex h-1/3 min-h-fit max-w-4xl flex-col justify-evenly rounded-lg bg-background p-8 text-start shadow-lg">
        <h1 className="mb-4 text-3xl text-status-red">
          Oops! An unknown error has occurred.
        </h1>
        <p className="mb-4 text-xl text-foreground">
          Please click the 'Reset Application' button to restore the
          application's state. If the error persists, please create an issue on
          our GitHub page. We apologize for any inconvenience this may have
          caused.
        </p>
        <div className="flex justify-center">
          <button
            onClick={resetErrorBoundary}
            className="mr-4 rounded bg-primary px-4 py-2 font-bold text-background hover:bg-ring"
          >
            Reset Application
          </button>
          <a
            href="https://github.com/logspace-ai/langflow/issues/new"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded bg-status-red px-4 py-2 font-bold text-background hover:bg-error-foreground"
          >
            Create Issue
          </a>
        </div>
      </div>
    </div>
  );
}
