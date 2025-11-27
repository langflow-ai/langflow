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
    <div className="flex w-full flex-1 flex-col justify-between overflow-auto overflow-x-hidden">
      <div className="flex w-full flex-1 flex-col">
        <div className="flex flex-col gap-4">
          <CustomBanner />
          <div className="flex w-full items-center justify-between gap-4 space-y-0.5">
            <div className="flex gap-2">
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
                    className="flex cursor-pointer text-menu"
                  />
                </Button>
              )}
              <div>
                <h1
                  className="text-menu text-xl font-medium"
                  data-testid="mainpage_title"
                >
                  {title}
                  {betaIcon && <span className="store-beta-icon">Beta</span>}
                </h1>
                <p className="text-secondary-font text-sm">{description}</p>
              </div>
            </div>
            <div className="flex-shrink-0">{button && button}</div>
          </div>
        </div>
        {/* <div className="flex shrink-0 px-6">
          {showSeparator && <Separator className="flex" />}
        </div> */}
        <div className="flex flex-1 mt-1">{children}</div>
      </div>
    </div>
  );
}
