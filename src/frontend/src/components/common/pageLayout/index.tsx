import { CustomBanner } from "@/customization/components/custom-banner";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { Button } from "../../ui/button";
import { Separator } from "../../ui/separator";
import ForwardedIconComponent from "../genericIconComponent";

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
    <div className="flex w-full flex-1 flex-col justify-between overflow-auto overflow-x-hidden bg-background">
      <div className="mx-auto flex w-full max-w-[1440px] flex-1 flex-col">
        <div className="flex flex-col gap-4 p-6 pt-0">
          <CustomBanner />
          <div className="flex w-full items-center justify-between gap-4 space-y-0.5 pb-2 pt-10">
            <div className="flex w-full flex-col">
              <div className="flex items-center gap-2">
                {backTo && (
                  <Button
                    unstyled
                    onClick={() => {
                      navigate(backTo);
                    }}
                    data-testid="back_page_button"
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
        <div className="flex shrink-0 px-6">
          <Separator className="flex" />
        </div>
        <div className="flex flex-1 p-6 pt-7">{children}</div>
      </div>
    </div>
  );
}
