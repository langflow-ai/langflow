import React, { useState } from "react";
import Footer from "@theme-original/Footer";
import { useThemeConfig } from "@docusaurus/theme-common";
import { useDocSearchKeyboardEvents } from '@docsearch/react';
import DocsChatbot from "@site/src/components/DocsChatbot";

export default function FooterWrapper(props) {
  const [isHovered, setIsHovered] = useState(false);
  const [chatbotOpen, setChatbotOpen] = useState(false);
  const searchButtonRef = React.useRef(null);
  const { customFields } = useThemeConfig();
  const docsChatbotProxyUrl = customFields?.docsChatbotProxyUrl ?? (typeof window !== "undefined" ? window.__DOCS_CHATBOT_PROXY_URL__ : undefined);

  useDocSearchKeyboardEvents({
    isOpen: chatbotOpen,
    onOpen: () => {
      if (docsChatbotProxyUrl) {
        setChatbotOpen(true);
      } else {
        searchButtonRef.current?.click();
      }
    },
  });

  const handleFloatingButtonClick = () => {
    if (docsChatbotProxyUrl) {
      setChatbotOpen(true);
    } else {
      document.querySelector('.DocSearch-Button')?.click();
    }
  };

  const floatingButton = (
    <div
      ref={searchButtonRef}
      onClick={handleFloatingButtonClick}
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
            padding: '8px 16px',
            borderRadius: '20px',
            color: '#000',
            fontSize: '14px',
            boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
          }}
        >
          Hi, how can I help you?
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
          alt={docsChatbotProxyUrl ? "Chat" : "Search"}
        />
      </div>
    </div>
  );

  return (
    <>
      <Footer {...props} />
      {floatingButton}
      <DocsChatbot proxyUrl={docsChatbotProxyUrl} open={chatbotOpen} onClose={() => setChatbotOpen(false)} />
    </>
  );
}
