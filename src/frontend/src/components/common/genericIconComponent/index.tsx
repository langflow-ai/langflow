import dynamicIconImports from "lucide-react/dynamicIconImports";
import { Suspense, forwardRef, lazy, memo } from "react";
import { IconComponentProps } from "../../../types/components";
import { nodeIconsLucide } from "../../../utils/styleUtils";
import { cn } from "../../../utils/utils";
import Loading from "../../ui/loading";

import { useEffect, useState } from "react";

// Thêm hàm xử lý để tạo SVG cho ScrapeGraphAI với thuộc tính React hợp lệ
const createScrapeGraphAI = (props: any) => {
  const { className, style, ref, "data-testid": dataTestId } = props;
  
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={style}
      ref={ref}
      data-testid={dataTestId}
    >
      {/* Cấu trúc của biểu tượng ScrapeGraphAI */}
      <path
        d="M12 2L2 7l10 5 10-5-10-5z"
      />
      <path
        d="M2 17l10 5 10-5"
      />
      <path
        d="M2 12l10 5 10-5"
      />
      <path
        fillRule="evenodd"
        d="M12 8a3 3 0 100-6 3 3 0 000 6z"
      />
    </svg>
  );
};

export const ForwardedIconComponent = memo(
  forwardRef(
    (
      {
        name,
        className,
        iconColor,
        stroke,
        strokeWidth,
        id = "",
        skipFallback = false,
        dataTestId = "",
      }: IconComponentProps,
      ref,
    ) => {
      const [showFallback, setShowFallback] = useState(false);

      useEffect(() => {
        const timer = setTimeout(() => {
          setShowFallback(true);
        }, 30);

        return () => clearTimeout(timer);
      }, []);

      // Xử lý đặc biệt cho trường hợp ScrapeGraphAI
      if (name === "ScrapeGraphAI") {
        const style = {
          strokeWidth: strokeWidth ?? 1.5,
          ...(stroke && { stroke: stroke }),
          ...(iconColor && { color: iconColor, stroke: stroke }),
        };

        return createScrapeGraphAI({
          className,
          style,
          ref,
          "data-testid": dataTestId ? dataTestId : id ? `${id}-${name}` : `icon-${name}`
        });
      }

      // Logic hiện tại cho các icon khác
      let TargetIcon =
        nodeIconsLucide[name] ||
        nodeIconsLucide[
          name
            ?.split("-")
            ?.map((x) => String(x[0]).toUpperCase() + String(x).slice(1))
            ?.join("")
        ];
      if (!TargetIcon) {
        if (!dynamicIconImports[name]) {
          TargetIcon = nodeIconsLucide["unknown"];
        } else TargetIcon = lazy(dynamicIconImports[name]);
      }

      const style = {
        strokeWidth: strokeWidth ?? 1.5,
        ...(stroke && { stroke: stroke }),
        ...(iconColor && { color: iconColor, stroke: stroke }),
      };

      if (!TargetIcon) {
        return null; // Render nothing until the icon is loaded
      }

      const fallback = showFallback ? (
        <div className={cn(className, "flex items-center justify-center")}>
          <Loading />
        </div>
      ) : (
        <div className={className}></div>
      );

      return (
        <Suspense fallback={skipFallback ? undefined : fallback}>
          <TargetIcon
            className={className}
            style={style}
            ref={ref}
            data-testid={
              dataTestId ? dataTestId : id ? `${id}-${name}` : `icon-${name}`
            }
          />
        </Suspense>
      );
    },
  ),
);

export default ForwardedIconComponent;