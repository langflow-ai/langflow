import React from 'react';

interface IconProps {
  name: string;
  size?: number;
  className?: string;
}

// All custom icons in one place
const customIcons = {
  agents: (size: number, className?: string) => (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <path
        d="M20.4444 17.5V20.5M11.5555 17.5V20.5M16 8.5V4M16 8.5C8.63619 8.5 2.66666 13.5368 2.66666 19.75C2.66666 25.9632 8.63619 28 16 28C23.3638 28 29.3333 25.9632 29.3333 19.75C29.3333 13.5368 23.3638 8.5 16 8.5Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  ),
  // Add more custom icons here as needed
  // example: (size: number, className?: string) => <svg>...</svg>
};

export default function CustomIcon({ name, size = 24, className }: IconProps) {
  const icon = customIcons[name as keyof typeof customIcons];
  return icon ? icon(size, className) : null;
} 