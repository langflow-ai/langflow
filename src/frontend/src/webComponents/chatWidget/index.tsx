import "../../bundle.min.js";

declare global {
  namespace JSX {
    interface IntrinsicElements {
      "langflow-chat": any;
    }
  }
}

export default function ChatWidget() {
  return (
    <div>
      <langflow-chat
        chat_position="top-right"
        flow_id="f0570b26-b2ba-42a4-91f4-aa56e520d380"
        host_url="http://localhost:7860"
      ></langflow-chat>
    </div>
  );
}
