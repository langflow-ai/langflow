import './index.css';
import r2wc from '@r2wc/react-to-web-component';
import PlaygroundComponent from './components/PlaygroundComponent';

declare global {
  interface Window {
    __styles: Record<string, string>;
  }
}

window.__styles = window.__styles ?? {};

class PlaygroundWebComponent extends r2wc(PlaygroundComponent, {
  shadow: "open",
}) {
  connectedCallback() {
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-ignore
    super.connectedCallback();

    queueMicrotask(() => {
      const css = window.__styles["playground-component"];
      if (css) {
        const template = document.createElement("template");
        template.innerHTML = `<style>${css}</style>`;
        this.shadowRoot?.appendChild(template.content.cloneNode(true));
      }
    });
  }
}

// Register the web component with a custom element name
customElements.define('playground-component', PlaygroundWebComponent);
