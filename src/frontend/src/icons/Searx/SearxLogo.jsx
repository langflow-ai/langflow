const SvgSearxLogo = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    xmlnsXlink="http://www.w3.org/1999/xlink"
    width="1em"
    height="1em"
    {...props}
  >
    <defs>
      <linearGradient id="Searx_logo_svg__b">
        <stop
          offset={0}
          style={{
            stopColor: "#fff",
            stopOpacity: 1,
          }}
        />
        <stop
          offset={1}
          style={{
            stopColor: "#fff",
            stopOpacity: 0,
          }}
        />
      </linearGradient>
      <linearGradient id="Searx_logo_svg__a">
        <stop
          offset={0}
          style={{
            stopColor: "#a9a9a9",
            stopOpacity: 1,
          }}
        />
        <stop
          offset={1}
          style={{
            stopColor: "#000",
            stopOpacity: 1,
          }}
        />
      </linearGradient>
      <linearGradient
        xlinkHref="#Searx_logo_svg__b"
        id="Searx_logo_svg__d"
        x1={120.689}
        x2={120.689}
        y1={239.618}
        y2={602.175}
        gradientUnits="userSpaceOnUse"
      />
      <radialGradient
        xlinkHref="#Searx_logo_svg__a"
        id="Searx_logo_svg__c"
        cx={294.459}
        cy={208.38}
        r={107.581}
        fx={294.459}
        fy={208.38}
        gradientUnits="userSpaceOnUse"
      />
      <filter
        id="Searx_logo_svg__e"
        width={1.26}
        height={1.294}
        x={-0.13}
        y={-0.147}
        colorInterpolationFilters="sRGB"
      >
        <feGaussianBlur stdDeviation={6.476} />
      </filter>
    </defs>
    <g transform="translate(-61.72 -34.87)">
      <path
        d="M70.523 34.87c-7.12 15.244-10.178 31.78-8.225 48.815 5.016 43.774 41.675 79.325 91.536 95.163-6.626-22.407-5.341-44.936 2.64-65.844-47.738-14.183-81.646-42.809-85.95-78.133zM303.779 36.214c7.12 15.243 10.178 31.78 8.225 48.815-5.016 43.774-41.675 79.324-91.536 95.163 6.626-22.408 5.341-44.937-2.64-65.845 47.738-14.182 81.646-42.808 85.95-78.133z"
        style={{
          fill: "#000",
          fillOpacity: 1,
          fillRule: "nonzero",
          stroke: "none",
        }}
      />
      <path
        d="M-5.09 259.06h18.416c6.22 0 11.228 16.683 11.228 37.404v172.837c0 20.722-5.007 37.404-11.228 37.404H-5.09c-6.22 0-11.228-16.682-11.228-37.404V296.464c0-20.721 5.008-37.403 11.228-37.403z"
        style={{
          fill: "#000",
          fillOpacity: 1,
          fillRule: "nonzero",
          stroke: "none",
        }}
        transform="rotate(-49.03)"
      />
      <path
        d="M402.04 208.38a107.581 107.581 0 1 1-215.162 0 107.581 107.581 0 1 1 215.163 0z"
        style={{
          fill: "url(#Searx_logo_svg__c)",
          fillOpacity: 1,
          fillRule: "nonzero",
          stroke: "none",
        }}
        transform="translate(-107.076 -60.61)"
      />
      <path
        d="M233.345 299.293a101.52 101.52 0 1 1-203.04 0 101.52 101.52 0 1 1 203.04 0z"
        style={{
          fill: "url(#Searx_logo_svg__d)",
          fillOpacity: 1,
          fillRule: "nonzero",
          stroke: "none",
        }}
        transform="matrix(.76866 0 0 .76866 85.803 -82.536)"
      />
      <path
        d="M210.617 156.357a27.274 27.274 0 1 1-54.548 0 27.274 27.274 0 1 1 54.548 0z"
        style={{
          fill: "#1a1a1a",
          fillOpacity: 1,
          fillRule: "nonzero",
          stroke: "none",
        }}
        transform="translate(5 -7.143)"
      />
      <path
        d="M203.546 203.329a5.556 5.556 0 1 1-11.112 0 5.556 5.556 0 1 1 11.112 0z"
        style={{
          fill: "#fff",
          fillOpacity: 1,
          fillRule: "nonzero",
          stroke: "none",
        }}
        transform="translate(1.485 -63.565)"
      />
      <rect
        width={2.239}
        height={159.438}
        x={19.526}
        y={337.84}
        rx={2.867}
        ry={9.001}
        style={{
          fill: "#fff",
          fillOpacity: 0.82211531,
          fillRule: "nonzero",
          stroke: "none",
          filter: "url(#Searx_logo_svg__e)",
        }}
        transform="matrix(.74467 -.84318 .84318 .74467 -35.543 -26.35)"
      />
    </g>
  </svg>
);
export default SvgSearxLogo;
