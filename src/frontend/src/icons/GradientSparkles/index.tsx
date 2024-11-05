import { Code } from "lucide-react";
import { forwardRef } from "react";
import ForwardedIconComponent from "../../components/genericIconComponent";

export const GradientInfinity = forwardRef<
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
      <Code stroke="url(#grad1)" ref={ref} {...props} />
    </>
  );
});

export const GradientSave = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return (
    <>
      <ForwardedIconComponent
        name="Save"
        stroke="url(#x-gradient)"
        ref={ref}
        {...props}
      />
    </>
  );
});

export const GradientGroup = (props) => {
  return (
    <>
      <svg width="0" height="0" style={{ position: "absolute" }}>
        <defs>
          <linearGradient id="grad3" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop className="gradient-start" offset="0%" />
            <stop className="gradient-end" offset="100%" />
          </linearGradient>
        </defs>
      </svg>
      <ForwardedIconComponent
        name="Combine"
        stroke={`${props.disabled ? "#64748B" : "url(#grad3)"}`}
        {...props}
      />
    </>
  );
};

export const GradientUngroup = (props) => {
  return (
    <>
      <svg width="0" height="0" style={{ position: "absolute" }}>
        <defs>
          <linearGradient id="grad4" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop className="gradient-start" offset="0%" />
            <stop className="gradient-end" offset="100%" />
          </linearGradient>
        </defs>
      </svg>
      <ForwardedIconComponent name="Ungroup" stroke="url(#grad4)" {...props} />
    </>
  );
};
