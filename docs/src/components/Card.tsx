import React from "react";

interface CardProps {
  title: string;
  href?: string;
  icon?: React.ReactNode;
  children?: React.ReactNode;
}

export default function Card({ title, href, icon, children }: CardProps) {
  const content = (
    <div className="lf-card">
      <div className="lf-card-header">
        {icon && <div className="lf-card-icon">{icon}</div>}
        <h4 className="lf-card-title">{title}</h4>
      </div>
      {children && <div className="lf-card-body">{children}</div>}
      {href && (
        <div className="lf-card-arrow">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path
              d="M6 3L11 8L6 13"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      )}
    </div>
  );

  if (href) {
    return (
      <a href={href} className="lf-card-link">
        {content}
      </a>
    );
  }

  return content;
}
