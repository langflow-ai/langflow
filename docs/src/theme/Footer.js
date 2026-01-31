import React from "react";
import Footer from "@theme-original/Footer";
import { useDocSearchKeyboardEvents } from '@docsearch/react';

export default function FooterWrapper(props) {
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
        document.querySelector('.DocSearch-Button')?.click();
      }}
      style={{
        position: 'fixed',
        right: '21px',
        bottom: '21px',
        zIndex: 100,
        cursor: 'pointer',
      }}
    >
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
