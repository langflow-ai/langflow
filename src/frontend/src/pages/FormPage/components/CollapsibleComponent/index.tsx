import React, { useState } from 'react';

type CollapsibleProps = {
  collapsed?: boolean;  // This will determine the initial state of the collapsible
  title?: string;       // This will be the title or trigger of the collapsible
  children?: React.ReactNode;  // This will be the content of the collapsible
};

const Collapsible: React.FC<CollapsibleProps> = ({ collapsed = true, title = "Toggle", children }) => {
    const [isCollapsed, setIsCollapsed] = useState(collapsed);

    const handleToggle = (e: React.MouseEvent) => {
        e.preventDefault();  // Prevent default button behavior
        setIsCollapsed(!isCollapsed);
    }

    return (
        <div className="mt-5 border-t border-gray-300 pt-5">
            <button onClick={handleToggle}>
                {title}
            </button>
            {!isCollapsed && <div className="content">{children}</div>}
        </div>
    );
}

export default Collapsible;
