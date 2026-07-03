const Scavio = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="1em"
    height="1em"
    viewBox="0 0 32 32"
    fill="none"
    {...props}
  >
    <rect width="32" height="32" rx="8" fill="#1D4ED8" />
    <circle cx="14" cy="14" r="5.5" stroke="white" strokeWidth="2" />
    <line x1="18" y1="18" x2="23" y2="23" stroke="white" strokeWidth="2" strokeLinecap="round" />
    <circle cx="14" cy="11.5" r="1" fill="white" />
    <circle cx="12" cy="14.5" r="1" fill="white" />
    <circle cx="16" cy="14.5" r="1" fill="white" />
  </svg>
);
export default Scavio;
