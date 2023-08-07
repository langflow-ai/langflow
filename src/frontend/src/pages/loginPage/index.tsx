import { FaApple, FaGithub } from "react-icons/fa";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { GoogleIcon } from "../../icons/Google";

export default function LoginPage() {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center bg-muted">
      <div className="flex w-72 flex-col items-center justify-center gap-2">
        <span className="mb-4 text-5xl">⛓️</span>
        <span className="mb-6 text-2xl font-semibold text-primary">
          Log in to LangFlow
        </span>
        <div className="flex w-full items-center justify-center gap-2">
          <Button variant="primary" className="w-full py-6">
            <FaApple className="h-6 w-6" />
          </Button>
          <Button variant="primary" className="w-full py-6">
            <FaGithub className="h-6 w-6" />
          </Button>
          <Button variant="primary" className="w-full py-6">
            <div className="h-6 w-6">
              <GoogleIcon />
            </div>
          </Button>
        </div>
        <span className="text-sm text-muted-foreground">or</span>
        <Input className="bg-background" placeholder="Email address" />
        <Input className="bg-background" placeholder="Password" />
        <Button variant="default" className="w-full">
          Login
        </Button>
        <Button variant="outline" className="mt-6 w-full">
          Don't have an account?&nbsp;<b>Sign Up</b>
        </Button>
      </div>
    </div>
  );
}
