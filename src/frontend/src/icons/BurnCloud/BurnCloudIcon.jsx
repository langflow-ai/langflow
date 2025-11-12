const BurnCloudIconSVG = ({ ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    role="img"
    aria-label="BurnCloud icon"
    fill="none"
    {...props}
  >
    <defs>
      <linearGradient
        id="burncloud-gradient"
        x2="1"
        gradientUnits="userSpaceOnUse"
        gradientTransform="matrix(-0.04 9.248 -11.433 -0.05 12.058 8.618)"
      >
        <stop offset="0" stopColor="#f7b52c" />
        <stop offset="1" stopColor="#e95513" />
      </linearGradient>
    </defs>
    <path
      fill="url(#burncloud-gradient)"
      d="M17.8 10.1c-.6-.9-1.4-1.9-1.4-1.9s-1.8-2.1-1.5-5.2c0 0-6.9 2.7-7 8.2 0 0-1-1.6-.8-4.6 0 0-2.2 2.1-2.5 5.5-2.1.7-3.8 2.5-3.8 4.3 0 2.5 2.7 4.6 5.9 4.6-2.4-.4-4.2-2-4.2-4 0-1.4.8-2.5 2-3.3.1 1.1.5 2.4.5 2.4s1.2 3.8 5.4 4.8a6.8 6.8 0 0 0 3.7-.3c1.3-.6 2.8-1.8 2.8-4.5 0 0 .1-2.7-1.5-4.1 0 0 2.1 5-1.8 6.5a4.8 4.8 0 0 1-3.9 0c-1.7-.7-3.8-2.5-3.5-7.2 0 0 1 3.4 3.2 4.7 0 0-2-5.8 3.9-9.8 0 0 .5 2.1 1.9 3.3.4.4 4 3.2 3.3 8 .7-.9 1.3-3.1.7-4.8 0 0-.1-.4-.4-.9 1.5.3 2.7 1.5 2.8 4.2.1 2.3-1.6 4.2-3.8 5 3-.4 5.4-2.7 5.4-5.6 0-2.8-2.2-5.1-5.4-5.3Z"
    />
  </svg>
);

export default BurnCloudIconSVG;
