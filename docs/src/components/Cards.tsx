import React from "react";

interface CardsProps {
  cols?: 1 | 2 | 3;
  children: React.ReactNode;
}

export default function Cards({ cols = 2, children }: CardsProps) {
  return (
    <div
      className="lf-cards"
      style={{
        gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
      }}
    >
      {children}
    </div>
  );
}
