import Header from "../headerComponent";
import { Separator } from "../ui/separator";

export default function PageLayout({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen w-full flex-col">
      <Header />
      <div className="flex h-full w-full flex-col justify-between overflow-auto bg-background px-16">
        <div className="flex w-full flex-col justify-between space-y-0.5 py-8 pb-2">
          <h2 className="text-2xl font-bold tracking-tight">{title}</h2>
          <p className="text-muted-foreground">{description}</p>
        </div>
        <Separator className="my-6 flex" />
        {children}
      </div>
    </div>
  );
}
