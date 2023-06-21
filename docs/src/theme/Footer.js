import React from 'react';
import Footer from '@theme-original/Footer';
import useDocusaurusContext from "@docusaurus/useDocusaurusContext";
import { MendableFloatingButton } from '@mendable/search';

export default function FooterWrapper(props) {
  const {
    siteConfig: { customFields },
  } = useDocusaurusContext();

  const iconSpan1 = React.createElement('img', {
    src: 'img/chain.png',
    style: { width: '40px' }
  }, null);

  const icon = React.createElement('div', {
    style: {
      color: '#ffffff',
      fontSize: '22px',
      width: '48px',
      height: '48px',
      margin: '0px',
      padding: '0px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      textAlign: 'center'
    }
  }, [iconSpan1]);

  const mendableFloatingButton = React.createElement(
    MendableFloatingButton,
    {
      style: { darkMode: true, accentColor: '#4051b5' },
      floatingButtonStyle: { color: '#ffffff', backgroundColor: '#010810' },
      anon_key: 'b7f52734-297c-41dc-8737-edbd13196394', // Mendable Search Public ANON key, ok to be public
      messageSettings: {
        openSourcesInNewTab: false,
      },
      showSimpleSearch: true,
      icon: icon,
    }
  );

  return (
    <>
      <Footer />
      {mendableFloatingButton}
    </>
  );
}