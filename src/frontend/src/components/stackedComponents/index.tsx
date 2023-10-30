import React, { ReactNode } from "react";

interface ElementStackProps {
  children: ReactNode[];
}

const ElementStack: React.FC<ElementStackProps> = ({ children }) => {
  return (
    <div
      className={`grid grid-cols-1`}
      style={{ display: "grid", gridAutoFlow: "row" }}
    >
      {children.map((child, index) => (
        <div
          key={index}
          style={{
            gridColumn: 1,
            gridRow: 1,
            transform: `translateX(${index * 0.1}rem)`,
            zIndex: children.length - index,
          }}
        >
          {child}
        </div>
      ))}
    </div>
  );
};

export default ElementStack;
