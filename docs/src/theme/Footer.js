import React, { useState } from "react";
import Footer from "@theme-original/Footer";
import { useDocSearchKeyboardEvents } from '@docsearch/react';

export default function FooterWrapper(props) {
  const [isHovered, setIsHovered] = useState(false);
  const searchButtonRef = React.useRef(null);

  useDocSearchKeyboardEvents({
    isOpen: false,
    onOpen: () => {
      searchButtonRef.current?.click();
    },
  });

  const searchButton = (
    <div
      ref={searchButtonRef}
      onClick={() => {
        // default click opens the search modal
        document.querySelector('.DocSearch-Button')?.click();
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        position: 'fixed',
        right: '21px',
        bottom: '21px',
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        cursor: 'pointer',
      }}
    >
      {isHovered && (
        <div
          style={{
            backgroundColor: "#f6f6f6",
            padding: '12px 16px',
            borderRadius: '16px',
            color: '#0f172a',
            fontSize: '14px',
            boxShadow: "0 8px 20px rgba(0,0,0,0.12)",
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            maxWidth: '280px',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div style={{ fontWeight: 600 }}>Hi, how can I help you?</div>
          <div style={{ height: 1, background: 'rgba(0,0,0,0.06)' }} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <a
              href="https://langflow.help/"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                color: '#2563eb',
                textDecoration: 'none',
                padding: '6px 8px',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                transition: 'background 120ms ease',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(37,99,235,0.08)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
            >
              <span style={{ fontSize: '16px' }}>↗</span>
              <span>Visit help center</span>
            </a>
            <button
              type="button"
              onClick={() => { document.querySelector('.DocSearch-Button')?.click(); }}
              style={{
                background: 'transparent',
                border: 'none',
                padding: '6px 8px',
                borderRadius: '8px',
                color: '#2563eb',
                textAlign: 'left',
                cursor: 'pointer',
                fontSize: '14px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                transition: 'background 120ms ease',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(37,99,235,0.08)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
            >
              <span style={{ fontSize: '16px' }}>🔍</span>
              <span>Search docs</span>
            </button>
          </div>
        </div>
      )}
      <div
        style={{
          backgroundColor: "#f6f6f6",
          borderRadius: "50%",
          width: "48px",
          height: "48px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
        }}
      >
        <img
          src="/img/langflow-icon-black-transparent.svg"
          style={{ width: "40px" }}
          alt="Search"
        />
      </div>
    </div>
  );

  return (
    <>
      <Footer {...props} />
      {searchButton}
    </>
  );
}
