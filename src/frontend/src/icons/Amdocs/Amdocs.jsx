import * as React from "react"
function SvgComponent(props) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      data-name="Layer 1"
      viewBox="0 0 1000 1000"
      {...props}
    >
      <defs>
        <linearGradient
          id="a"
          x1={204.46}
          x2={784.6}
          y1={9969.45}
          y2={9969.45}
          gradientTransform="matrix(1 0 0 -1 -5.21 10469.45)"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset={0.02} stopColor="#fdb515" />
          <stop offset={0.1} stopColor="#fba91e" />
          <stop offset={0.26} stopColor="#f68935" />
          <stop offset={0.47} stopColor="#f05656" />
          <stop offset={0.73} stopColor="#ed1684" />
          <stop offset={0.77} stopColor="#eb0d8c" />
        </linearGradient>
      </defs>
      <path
        fill="url(#a)"
        d="M512.4 281H255.71l25.46 87.46h231.56a44 44 0 0 1 43.9 43.9v43.9H337.47a131.36 131.36 0 1 0 0 262.72H512.4c72.38 0 131.36-59 131-131.36V412.37c.03-72.37-58.62-131.03-131-131.37M556 586.63a43.76 43.76 0 0 1-43.56 43.89H337.47a43.82 43.82 0 0 1 0-87.46H556Z"
      />
      <path
        fill="#eb0d8c"
        d="M768.76 456.27 689 456.27 689 543.73 793.89 543.73 768.76 456.27z"
      />
    </svg>
  )
}
export default SvgComponent