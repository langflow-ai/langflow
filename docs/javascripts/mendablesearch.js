document.addEventListener('DOMContentLoaded', () => {
  // Load the external dependencies
  function loadScript(src, onLoadCallback) {
    const script = document.createElement('script');
    script.src = src;
    script.onload = onLoadCallback;
    document.head.appendChild(script);
  }

  function createRootElement() {
    const rootElement = document.createElement('div');
    rootElement.id = 'my-component-root';
    document.body.appendChild(rootElement);
    return rootElement;
  }

  

  function initializeMendable() {
    const rootElement = createRootElement();
    const { MendableFloatingButton } = Mendable;
    

    const iconSpan1 = React.createElement('img', {
      src: 'img/chain.png',
      style: {width: '40px'}
    }, null);

    const icon = React.createElement('p', {
      style: { color: '#ffffff', fontSize: '22px',width: '48px', height: '48px', margin: '0px', padding: '0px', display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center' },
    }, [iconSpan1]);

    
    

    const mendableFloatingButton = React.createElement(
      MendableFloatingButton,
      {
        style: { darkMode: false, accentColor: '#010810' },
        floatingButtonStyle: { color: '#ffffff', backgroundColor: '#010810' },
        anon_key: 'b7f52734-297c-41dc-8737-edbd13196394', // Mendable Search Public ANON key, ok to be public
        messageSettings: {
          openSourcesInNewTab: false,
        },
        icon: icon,
      }
    );

    ReactDOM.render(mendableFloatingButton, rootElement);
  }

  loadScript('https://unpkg.com/react@17/umd/react.production.min.js', () => {
    loadScript('https://unpkg.com/react-dom@17/umd/react-dom.production.min.js', () => {
      loadScript('https://unpkg.com/@mendable/search@0.0.93/dist/umd/mendable.min.js', initializeMendable);
    });
  });
});
