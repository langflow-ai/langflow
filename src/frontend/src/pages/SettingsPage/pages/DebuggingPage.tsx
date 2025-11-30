import { IS_CLERK_AUTH } from "@/clerk/auth";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useOrganization, useUser } from "@clerk/clerk-react";
import { useCallback, useMemo, useState } from "react";

function ClerkDebuggingContent() {
  const [copiedId, setCopiedId] = useState<"user" | "org" | null>(null);
  const { user, isLoaded: isUserLoaded } = useUser();
  const { organization, isLoaded: isOrganizationLoaded } = useOrganization();

  const userId = useMemo(
    () => (isUserLoaded ? user?.id ?? "Unavailable" : "Loading..."),
    [isUserLoaded, user?.id],
  );

  const orgId = useMemo(
    () =>
      isOrganizationLoaded
        ? organization?.id ?? "No active organization"
        : "Loading...",
    [isOrganizationLoaded, organization?.id],
  );

  const handleCopy = useCallback((value: string, key: "user" | "org") => {
    if (typeof navigator === "undefined" || !navigator.clipboard) return;

    navigator.clipboard.writeText(value).then(() => {
      setCopiedId(key);
      setTimeout(() => setCopiedId(null), 1500);
    });
  }, []);

  return (
    <div className="flex h-full w-full flex-col gap-6">
      <div className="flex w-full flex-col gap-2">
        <h2 className="flex items-center text-lg font-semibold tracking-tight">
          Debugging
          <ForwardedIconComponent
            name="Bug"
            className="ml-2 h-5 w-5 text-primary"
          />
        </h2>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card className="h-full bg-card/60 backdrop-blur">
          <CardHeader>
            <CardTitle>User ID</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between rounded-md border border-border bg-background/80 px-3 py-2 font-mono text-sm">
              <span className="truncate" title={userId}>
                {userId}
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => handleCopy(userId, "user")}
                className="ml-3"
                disabled={!isUserLoaded}
              >
                <ForwardedIconComponent
                  name={copiedId === "user" ? "Check" : "Copy"}
                  className="h-4 w-4"
                />
                <span className="sr-only">Copy user id</span>
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="h-full bg-card/60 backdrop-blur">
          <CardHeader>
            <CardTitle>Organization ID</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between rounded-md border border-border bg-background/80 px-3 py-2 font-mono text-sm">
              <span className="truncate" title={orgId}>
                {orgId}
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => handleCopy(orgId, "org")}
                className="ml-3"
                disabled={!isOrganizationLoaded}
              >
                <ForwardedIconComponent
                  name={copiedId === "org" ? "Check" : "Copy"}
                  className="h-4 w-4"
                />
                <span className="sr-only">Copy organization id</span>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function NonClerkDebuggingMessage() {
  return (
    <div className="flex h-full w-full flex-col gap-4">
      <div className="flex items-center gap-2">
        <ForwardedIconComponent
          name="ShieldOff"
          className="h-5 w-5 text-muted-foreground"
        />
        <h2 className="text-lg font-semibold tracking-tight">Debugging</h2>
      </div>
      <Card className="bg-card/60 backdrop-blur">
        <CardHeader>
          <CardTitle>Clerk not enabled</CardTitle>
          <CardDescription>
            This workspace is not configured to use Clerk authentication, so no
            Clerk identifiers are available.
          </CardDescription>
        </CardHeader>
      </Card>
    </div>
  );
}

export default function DebuggingPage() {
  if (!IS_CLERK_AUTH) {
    return <NonClerkDebuggingMessage />;
  }

  return <ClerkDebuggingContent />;
}
