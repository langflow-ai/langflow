const SendHQ = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="1em"
    height="1em"
    fill="none"
    viewBox="0 0 32 32"
    {...props}
  >
    <defs>
      <linearGradient
        id="sendhq-icon-gradient"
        x1="0"
        y1="0"
        x2="32"
        y2="32"
        gradientUnits="userSpaceOnUse"
      >
        <stop offset="0" stopColor="#fbad41" />
        <stop offset="1" stopColor="#f6821f" />
      </linearGradient>
    </defs>
    <rect width="32" height="32" rx="9" fill="url(#sendhq-icon-gradient)" />
    <path
      d="M 20.5 11.5 A 4.5 4.5 0 1 0 16 16 A 4.5 4.5 0 1 1 11.5 20.5"
      fill="none"
      stroke="#ffffff"
      strokeWidth="3.4"
      strokeLinecap="round"
    />
  </svg>
);
export default SendHQ;
