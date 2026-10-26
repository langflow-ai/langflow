import type { ReactNode } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { SidebarTrigger } from "@/components/ui/sidebar";

interface EvalsPageShellProps {
  title: string;
  titleTestId: string;
  back?: ReactNode;
  actions?: ReactNode;
  meta?: ReactNode;
  children: ReactNode;
}

/** The Files and Knowledge page frame: same container, padding and title row. */
export default function EvalsPageShell({
  title,
  titleTestId,
  back,
  actions,
  meta,
  children,
}: EvalsPageShellProps) {
  return (
    <div className="flex h-full w-full flex-col overflow-y-auto">
      <div className="flex h-full w-full flex-col xl:container">
        <div className="flex flex-1 flex-col justify-start px-5 pt-10">
          <div className="flex h-full flex-col justify-start">
            <div className="flex items-center justify-between gap-4 pb-4">
              <div className="flex min-w-0 items-center gap-1">
                <div className="h-7 w-10 transition-all group-data-[open=true]/sidebar-wrapper:md:w-0 lg:hidden">
                  <div className="relative left-0 opacity-100 transition-all group-data-[open=true]/sidebar-wrapper:md:opacity-0">
                    <SidebarTrigger>
                      <ForwardedIconComponent
                        name="PanelLeftOpen"
                        aria-hidden="true"
                      />
                    </SidebarTrigger>
                  </div>
                </div>
                {back}
                <h1
                  className="min-w-0 truncate text-xl font-semibold"
                  data-testid={titleTestId}
                >
                  {title}
                </h1>
              </div>
              {actions && (
                <div className="flex shrink-0 items-center gap-2">
                  {actions}
                </div>
              )}
            </div>
            {meta && <div className="-mt-2 pb-4">{meta}</div>}
            <div className="flex h-full flex-col">{children}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
