import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { FcGoogle } from "react-icons/fc";

interface OAuthLoginButtonsProps {
  className?: string;
  providers?: string[];
}

export default function OAuthLoginButtons({
  className,
  providers = [],
}: OAuthLoginButtonsProps) {
  if (providers.length === 0) {
    return null;
  }

  const handleOAuthLogin = (provider: string) => {
    window.location.href = `/api/v1/oauth/${provider}/login`;
  };

  return (
    <div className={className}>
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <Separator className="w-full" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-background px-2 text-muted-foreground">
            Or continue with
          </span>
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-2">
        {providers.includes("google") && (
          <Button
            variant="outline"
            onClick={() => handleOAuthLogin("google")}
            className="w-full"
          >
            <FcGoogle className="mr-2 h-4 w-4" />
            Continue with Google
          </Button>
        )}

        {providers.includes("microsoft") && (
          <Button
            variant="outline"
            onClick={() => handleOAuthLogin("microsoft")}
            className="w-full"
          >
            Continue with Microsoft
          </Button>
        )}
      </div>
    </div>
  );
}
