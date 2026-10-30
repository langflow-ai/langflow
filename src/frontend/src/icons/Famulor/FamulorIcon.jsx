const SvgFamulor = ({ isDark: _isDark, isdark: _isdark, ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={32}
    height={32}
    viewBox="0 0 32 32"
    fill="none"
    role="img"
    aria-label="Famulor"
    {...props}
  >
    <rect width="32" height="32" rx="9" fill="#1FD5FA" />
    <rect x="4" y="9" width="24" height="14" rx="7" fill="#0F1113" />
    <circle cx="21" cy="16" r="5.2" fill="#FFFFFF" />
  </svg>
);

export default SvgFamulor;
