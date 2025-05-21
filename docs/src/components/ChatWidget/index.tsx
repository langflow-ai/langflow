import React, { useEffect } from 'react';

// Component to load the chat widget script
const ChatScriptLoader = () => {
  useEffect(() => {
    if (!document.querySelector('script[src*="langflow-embedded-chat"]')) {
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/gh/langflow-ai/langflow-embedded-chat@main/dist/build/static/js/bundle.min.js';
      script.async = true;
      document.body.appendChild(script);
    }
  }, []);

  return null;
};

declare global {
    namespace JSX {
      interface IntrinsicElements {
        "langflow-chat": any;
      }
    }
  }

  export default function ChatWidget({ className }) {
    return (
      <div className={className}>
        <ChatScriptLoader />
        <langflow-chat
          host_url="https://c822-73-64-93-151.ngrok-free.app"
          flow_id="dcbed533-859f-4b99-b1f5-16fce884f28f"
        ></langflow-chat>
      </div>
    );
  }