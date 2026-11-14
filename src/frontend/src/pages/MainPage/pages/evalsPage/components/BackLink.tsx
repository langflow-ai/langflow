import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";

export default function BackLink({ to, label }: { to: string; label: string }) {
  const navigate = useCustomNavigate();
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={label}
      onClick={() => navigate(to)}
    >
      <ForwardedIconComponent name="ArrowLeft" className="h-4 w-4" />
    </Button>
  );
}
