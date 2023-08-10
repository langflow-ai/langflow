import { useNavigate } from "react-router-dom";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";

export default function LoginAdminPage() {
  const navigate = useNavigate();

  function loginAdmin() {
    navigate("/admin/");
  }

  return (
    <div className="flex h-full w-full flex-col items-center justify-center bg-muted">
      <div className="flex w-72 flex-col items-center justify-center gap-2">
        <span className="mb-4 text-5xl">⛓️</span>
        <span className="mb-6 text-2xl font-semibold text-primary">Admin</span>
        <Input className="bg-background" placeholder="Email address" />
        <Input className="bg-background" placeholder="Password" />
        <Button
          onClick={() => {
            loginAdmin();
          }}
          variant="default"
          className="w-full"
        >
          Login
        </Button>
      </div>
    </div>
  );
}
