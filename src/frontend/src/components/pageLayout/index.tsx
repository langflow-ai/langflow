import { CustomBanner } from "@/customization/components/custom-banner";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import ForwardedIconComponent from "../genericIconComponent";
import { Button } from "../ui/button";
import { Separator } from "../ui/separator";

export default function PageLayout({
  title,
  description,
  children,
  button,
  betaIcon,
  backTo = "",
}: {
  title: string;
  description: string;
  children: React.ReactNode;
  button?: React.ReactNode;
  betaIcon?: boolean;
  backTo?: string;
}) {
  const navigate = useCustomNavigate();

  return (
    <div className="flex h-full w-full flex-col justify-between overflow-auto bg-background px-6 pt-10">
      <div className="mx-auto h-full w-full max-w-[1440px]">
        <div className="flex flex-col gap-4">
          <CustomBanner />
          <div className="flex w-full items-center justify-between gap-4 space-y-0.5 py-2">
            <div className="flex w-full flex-col">
              <div className="flex items-center gap-2">
                {backTo && (
                  <Button
                    unstyled
                    onClick={() => {
                      navigate(backTo);
                    }}
                  >
                    <ForwardedIconComponent
                      name="ChevronLeft"
                      className="flex cursor-pointer"
                    />
                  </Button>
                )}
                <h2
                  className="text-2xl font-bold tracking-tight"
                  data-testid="mainpage_title"
                >
                  {title}
                  {betaIcon && <span className="store-beta-icon">Beta</span>}
                </h2>
              </div>
              <p className="text-muted-foreground">{description}</p>
            </div>
            <div className="flex-shrink-0">{button && button}</div>
          </div>
        </div>
        <Separator className="my-6 flex" />
        {children}
      </div>
    </div>
  );
}
