const WebRouterIcon = ({ isDark = false, ...props }) => {
  const color = isDark ? "#eeeae0" : "#202c26";

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="1em"
      height="1em"
      viewBox="-2 -15 35 35"
      fill="none"
      {...props}
    >
      <g fill={color}>
        <rect
          x="6"
          y="-13"
          width="3"
          height="14"
          rx="1.5"
          transform="rotate(-10 7.5 -6)"
        />
        <rect
          x="22"
          y="-13"
          width="3"
          height="14"
          rx="1.5"
          transform="rotate(10 23.5 -6)"
        />
        <rect
          x="1"
          y="1"
          width="29"
          height="17"
          rx="1"
          fill="none"
          stroke={color}
          strokeWidth="2"
        />
        <path d="M8 9h2v3H8z M15 9h2v3h-2z M22 9h2v3h-2z" />
      </g>
    </svg>
  );
};

export default WebRouterIcon;
