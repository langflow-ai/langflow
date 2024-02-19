import { crashComponentPropsType } from "../../types/components";

export default function CrashErrorComponent({
  error,
  resetErrorBoundary,
}: crashComponentPropsType): JSX.Element {
  return (
    <div className="z-50 flex h-screen w-screen items-center justify-center bg-foreground bg-opacity-50">
      <div className="flex h-screen w-screen flex-col  bg-background text-start shadow-lg">
        <div className="m-auto grid w-1/2 justify-center gap-5 text-center">
          <div>
            <h1 className="text-3xl text-status-red">
              🚀 Whoops! We've Hit a Snag.
            </h1>
            <small>
              Hey there, it looks like we've encountered a bit of a hiccup.
            </small>
          </div>
          <div>
            <p className="mb-4 text-xl text-foreground">
              But don't worry, it happens to the best of us! We're all about
              making things better together.
            </p>
          </div>

          <div>
            <p>
              🔧 Quick Fix: Try hitting the{" "}
              <span className="font-bold">'Restart the Adventure'</span> button
              to get things moving again. It's like a magic wand for minor
              glitches!
            </p>
          </div>

          <div>
            <p>
              📝 Still Stuck? Let's Solve It Together: If our magic wand didn't
              do the trick, we'd love your help to dig a bit deeper. By
              reporting this hiccup on our{" "}
              <a
                href="https://github.com/logspace-ai/langflow/issues/new"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-blue-600 hover:underline dark:text-blue-500"
              >
                GitHub
              </a>{" "}
              page, you're not just fixing your own experience but also helping
              the whole community.
            </p>
          </div>

          <div className="mt-4 flex justify-center">
            <button
              onClick={resetErrorBoundary}
              className="cursor-pointer rounded-lg border-2 border-blue-600 px-3 py-2 font-bold text-blue-600 hover:bg-blue-600 hover:text-blue-100"
            >
              Restart the Adventure
            </button>

            <a
              href="https://github.com/logspace-ai/langflow/issues/new"
              target="_blank"
              rel="noopener noreferrer"
            >
              <button className="ml-3 cursor-pointer rounded-lg border-2 border-gray-600 px-3 py-2 font-bold text-gray-600 hover:bg-gray-600 hover:text-gray-100">
                Report on GitHub
              </button>
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
