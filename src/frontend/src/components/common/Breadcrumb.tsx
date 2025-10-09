import {
  Breadcrumb as BreadcrumbRoot,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";

export interface BreadcrumbItemType {
  label: string;
  href?: string;
  beta?: boolean;
}

interface BreadcrumbProps {
  items: BreadcrumbItemType[];
  className?: string;
}

export default function Breadcrumb({ items, className }: BreadcrumbProps) {
  const navigate = useCustomNavigate();

  const handleClick = (href: string) => {
    navigate(href);
  };

  return (
    <BreadcrumbRoot className={className}>
      <BreadcrumbList>
        {items.map((item, index) => {
          const isLast = index === items.length - 1;

          return (
            <div key={index} className="flex items-center gap-1.5">
              <BreadcrumbItem>
                {item.href && !isLast ? (
                  <BreadcrumbLink
                    className="cursor-pointer"
                    onClick={() => handleClick(item.href!)}
                  >
                    {item.label}
                  </BreadcrumbLink>
                ) : (
                  <BreadcrumbPage>
                    {item.label}
                    {item.beta && (
                      <span className="ml-1 align-top text-[10px] text-muted-foreground">
                        (beta)
                      </span>
                    )}
                  </BreadcrumbPage>
                )}
              </BreadcrumbItem>
              {/* {!isLast && <BreadcrumbSeparator>/</BreadcrumbSeparator>} */}
            </div>
          );
        })}
      </BreadcrumbList>
    </BreadcrumbRoot>
  );
}
