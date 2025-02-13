import { XCircle } from "lucide-react";
import { crashComponentPropsType } from "../../../types/components";
import { Button } from "../../ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "../../ui/card";

export default function CrashErrorComponent({
  error,
  resetErrorBoundary,
}: crashComponentPropsType): JSX.Element {
  return (
    <div className="bg-foreground/50 z-50 flex h-screen w-screen items-center justify-center">
      <div className="bg-background flex h-screen w-screen flex-col text-start shadow-lg">
        <div className="m-auto grid w-1/2 justify-center gap-5 text-center">
          <Card className="p-8">
            <CardHeader>
              <div className="m-auto">
                <XCircle strokeWidth={1.5} className="h-16 w-16" />
              </div>
              <div>
                <p className="text-foreground mb-4 text-xl">
                  Sorry, we found an unexpected error!
                </p>
              </div>
            </CardHeader>

            <CardContent className="grid">
              <div>
                <p>
                  Please report errors with detailed tracebacks on the{" "}
                  <a
                    href="https://github.com/langflow-ai/langflow/issues"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium hover:underline"
                  >
                    GitHub Issues
                  </a>{" "}
                  page.
                  <br></br>
                  Thank you!
                </p>
              </div>
            </CardContent>

            <CardFooter>
              <div className="m-auto mt-4 flex justify-center">
                <Button onClick={resetErrorBoundary}>Restart Langflow</Button>

                <a
                  href="https://github.com/langflow-ai/langflow/issues/new"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Button className="ml-3" ignoreTitleCase variant={"outline"}>
                    Report on GitHub
                  </Button>
                </a>
              </div>
            </CardFooter>
          </Card>
        </div>
      </div>
    </div>
  );
}
