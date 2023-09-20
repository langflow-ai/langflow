import { forwardRef } from "react";

export const GradientSparkles = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return (
    <>
      <svg width="0" height="0" style={{ position: "absolute" }}>
        <defs>
          <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop className="gradient-start" offset="0%" />
            <stop className="gradient-end" offset="100%" />
          </linearGradient>
        </defs>
      </svg>
      {/* this svg comes from the source code of lucide,
         we do not use the import because it crashes the ui (why? no one knows...).
         source code from the used svg:
         https://github.com/lucide-icons/lucide/blob/a4076db69b52ff0debc383f76d4d671c3bad5345/icons/infinity.svg?short_path=f79de91
         */}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke="url(#grad1)"
        ref={ref}
        {...props}
      >
        <path d="M12 12c-2-2.67-4-4-6-4a4 4 0 1 0 0 8c2 0 4-1.33 6-4Zm0 0c2 2.67 4 4 6 4a4 4 0 0 0 0-8c-2 0-4 1.33-6 4Z" />
      </svg>
    </>
  );
});
