import type { To } from "react-router-dom";
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
  showSeparator = true,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
  button?: React.ReactNode;
  betaIcon?: boolean;
  backTo?: To;
  showSeparator?: boolean;
}) {
  const navigate = useCustomNavigate();

  return (
    <div className="flex w-full flex-1 flex-col justify-between overflow-auto overflow-x-hidden bg-background">
      <div className="flex w-full flex-1 flex-col">
        <div className="flex flex-col gap-4">
          <CustomBanner />
          <div className="flex w-full items-center justify-between gap-4 space-y-0.5 pt-4">
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
                  className="text-[#350E84] text-[21px] font-medium leading-normal not-italic"
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
          {showSeparator && <Separator className="flex" />}
        </div>
        <div className="flex flex-1 p-2">{children}</div>
      </div>
    </div>
  );
}
