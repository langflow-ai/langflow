import { CustomBanner } from "@/customization/components/custom-banner";
import { Separator } from "../ui/separator";

export default function PageLayout({
  title,
  description,
  children,
  button,
  betaIcon,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
  button?: React.ReactNode;
  betaIcon?: boolean;
}) {
  return (
    <div className="flex h-full w-full flex-col justify-between overflow-auto bg-background px-16 pt-6">
      <div className="flex flex-col gap-4">
        <CustomBanner />
        <div className="flex w-full items-center justify-between gap-4 space-y-0.5 py-2">
          <div className="flex w-full flex-col">
            <h2
              className="text-2xl font-bold tracking-tight"
              data-testid="mainpage_title"
            >
              {title}
              {betaIcon && <span className="store-beta-icon">BETA</span>}
            </h2>
            <p className="text-muted-foreground">{description}</p>
          </div>
          <div className="flex-shrink-0">{button && button}</div>
        </div>
      </div>
      <Separator className="my-6 flex" />
      {children}
    </div>
  );
}
