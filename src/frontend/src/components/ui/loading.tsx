import type { SVGProps } from "react";

export type LoadingProps = SVGProps<SVGSVGElement> & {
  size?: number;
};

// https://github.com/feathericons/feather/issues/695#issuecomment-1503699643
export const Loading = ({ size = 24, ...props }: LoadingProps) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    className="feather feather-circle"
    {...props}
    data-testid="loading-icon"
  >
    <circle cx={12} cy={12} r={10} strokeDasharray={63} strokeDashoffset={21}>
      <animateTransform
        attributeName="transform"
        type="rotate"
        from="0 12 12"
        to="360 12 12"
        dur="2s"
        repeatCount="indefinite"
      />
      <animate
        attributeName="stroke-dashoffset"
        dur="8s"
        repeatCount="indefinite"
        keyTimes="0; 0.5; 1"
        values="-16; -47; -16"
        calcMode="spline"
        keySplines="0.4 0 0.2 1; 0.4 0 0.2 1"
      />
    </circle>
  </svg>
);
export default Loading;
