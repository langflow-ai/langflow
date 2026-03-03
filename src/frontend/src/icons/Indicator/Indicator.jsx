export const IndicatorComponent = ({ className, ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="6"
    height="6"
    viewBox="0 0 6 6"
    fill="none"
    className={className}
    {...props}
  >
    <circle cx="3" cy="3" r="3" fill="#F87171" />
  </svg>
);
