import r2wc from '@r2wc/react-to-web-component';
import PlaygroundComponent from './components/PlaygroundComponent';

// Convert the React component to a web component
const PlaygroundWebComponent = r2wc(PlaygroundComponent);

// Register the web component with a custom element name
customElements.define('playground-component', PlaygroundWebComponent);
