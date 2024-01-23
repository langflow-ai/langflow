import Header from "../headerComponent";
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
    <div className="flex h-screen w-full flex-col">
      <Header />
      <div className="flex h-full w-full flex-col justify-between overflow-auto bg-background px-16">
        <div className="flex w-full items-center justify-between gap-4 space-y-0.5 py-8 pb-2">
          <div className="flex w-full flex-col">
            <h2 className="text-2xl font-bold tracking-tight">
              {title}
              {betaIcon && <span className="store-beta-icon">BETA</span>}
            </h2>
            <p className="text-muted-foreground">{description}</p>
          </div>
          <div className="flex-shrink-0">{button && button}</div>
        </div>
        <Separator className="my-6 flex" />
        {children}
      </div>
    </div>
  );
}
