import React, { forwardRef } from "react";

const SvgBrightData = forwardRef((props, ref) => (
  <svg
    width="24"
    height="24"
    viewBox="0 0 100 100"
    xmlns="http://www.w3.org/2000/svg"
    ref={ref}
    {...props}
  >
    <defs>
      <linearGradient id="bgGradient" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" style={{ stopColor: "#4285f4", stopOpacity: 1 }} />
        <stop offset="100%" style={{ stopColor: "#1a73e8", stopOpacity: 1 }} />
      </linearGradient>
    </defs>
    
    {/* Blue rounded background */}
    <rect 
      x="0" 
      y="0" 
      width="100" 
      height="100" 
      rx="20" 
      ry="20" 
      fill="url(#bgGradient)" 
    />
    
    {/* White "i" letter body */}
    <rect 
      x="42" 
      y="45" 
      width="16" 
      height="40" 
      rx="2" 
      ry="2" 
      fill="white" 
    />
    
    {/* White flame dot (top of "i") */}
    <path 
      d="M 50 15 
         C 45 20, 40 25, 42 32
         C 44 35, 46 36, 48 35
         C 49 33, 50 31, 52 32
         C 54 33, 56 35, 58 32
         C 60 25, 55 20, 50 15 Z" 
      fill="white" 
    />
    
    {/* Small inner flame detail */}
    <path 
      d="M 50 20
         C 48 22, 46 24, 47 28
         C 48 30, 50 29, 52 28
         C 53 24, 52 22, 50 20 Z"
      fill="#4285f4" 
      opacity="0.3" 
    />
  </svg>
));

SvgBrightData.displayName = "SvgBrightData";

export default SvgBrightData;