import React, { useState, useEffect } from "react";
import { useColorMode } from "@docusaurus/theme-common";
import Link from "@docusaurus/Link";
import SearchBar from "@theme/SearchBar";
import ThemedImage from "@theme/ThemedImage";
import Icon from "@site/src/components/icon";
import OriginalNavbar from "@theme-original/Navbar";

export default function Navbar(props) {
  // Check if we're on mobile
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    
    checkMobile();
    window.addEventListener('resize', checkMobile);
    
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // If mobile, use original Docusaurus navbar
  if (isMobile) {
    return <OriginalNavbar {...props} />;
  }
  // Social links (reuse from config or hardcode for now)
  const socialLinks = [
    {
      href: "https://github.com/langflow-ai/langflow",
      icon: "github",
      label: "GitHub",
    },
    { href: "https://x.com/langflow_ai", icon: "x", label: "X" },
    { href: "https://discord.gg/langflow", icon: "discord", label: "Discord" },
  ];

  // Theme toggle (use Docusaurus v2 colorMode)
  const { colorMode, setColorMode } = useColorMode();

  return (
    <nav className="lf-navbar">
      {/* Left: Logo */}
      <Link to="/" className="lf-navbar-logo">
        <ThemedImage
          alt="Langflow Logo"
          sources={{
            light: "/img/lf-docs-light.svg",
            dark: "/img/lf-docs-dark.svg",
          }}
        />
      </Link>

      {/* Center: Algolia Search */}
      <div className="lf-navbar-search">
        <div className="navbar__search">
          <SearchBar />
        </div>
      </div>

      {/* Right: Download, Socials, Theme Toggle */}
      <div className="lf-navbar-actions">
        <Link
          to="https://www.langflow.org/desktop"
          className="lf-navbar-download-btn"
        >
          Download
          <Icon name="MonitorDown" size={16} />
        </Link>

        <div className="lf-navbar-social-icons">
          {socialLinks.map((link) => (
            <a
              key={link.icon}
              href={link.href}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={link.label}
              className="lf-navbar-social-icon"
            >
              {link.icon === "github" && (
                <svg width="18" height="18" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 .5C5.73.5.5 5.73.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56 0-.28-.01-1.02-.02-2-3.2.7-3.88-1.54-3.88-1.54-.53-1.34-1.3-1.7-1.3-1.7-1.06-.72.08-.71.08-.71 1.17.08 1.78 1.2 1.78 1.2 1.04 1.78 2.73 1.27 3.4.97.11-.75.41-1.27.74-1.56-2.55-.29-5.23-1.28-5.23-5.7 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11.1 11.1 0 0 1 2.9-.39c.98 0 1.97.13 2.9.39 2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.84 1.19 3.1 0 4.43-2.69 5.41-5.25 5.7.42.36.79 1.09.79 2.2 0 1.59-.01 2.87-.01 3.26 0 .31.21.68.8.56C20.71 21.39 24 17.08 24 12c0-6.27-5.23-11.5-12-11.5z" />
                </svg>
              )}
              {link.icon === "x" && (
                <svg width="18" height="18" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                </svg>
              )}
              {link.icon === "discord" && (
                <svg width="18" height="18" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M20.317 4.369A19.791 19.791 0 0 0 16.885 3.1a.074.074 0 0 0-.079.037c-.34.607-.719 1.396-.984 2.013a18.524 18.524 0 0 0-5.624 0 12.51 12.51 0 0 0-.997-2.013.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.684 4.369a.07.07 0 0 0-.032.027C.533 9.09-.32 13.579.099 18.021a.082.082 0 0 0 .031.056c2.104 1.548 4.13 2.488 6.123 3.104a.077.077 0 0 0 .084-.027c.472-.65.893-1.34 1.248-2.063a.076.076 0 0 0-.041-.104c-.671-.253-1.31-.558-1.927-.892a.077.077 0 0 1-.008-.128c.13-.098.26-.2.384-.304a.074.074 0 0 1 .077-.01c4.014 1.83 8.36 1.83 12.326 0a.073.073 0 0 1 .078.009c.124.104.254.206.384.304a.077.077 0 0 1-.007.128c-.617.334-1.256.639-1.928.892a.076.076 0 0 0-.04.105c.36.722.78 1.412 1.247 2.062a.076.076 0 0 0 .084.028c1.993-.616 4.02-1.556 6.124-3.104a.077.077 0 0 0 .03-.055c.5-5.177-.838-9.637-3.549-13.625a.061.061 0 0 0-.03-.028zM8.02 15.331c-1.183 0-2.156-1.085-2.156-2.419 0-1.333.955-2.418 2.156-2.418 1.21 0 2.175 1.094 2.156 2.418 0 1.334-.955 2.419-2.156 2.419zm7.974 0c-1.183 0-2.156-1.085-2.156-2.419 0-1.333.955-2.418 2.156-2.418 1.21 0 2.175 1.094 2.156 2.418 0 1.334-.946 2.419-2.156 2.419z" />
                </svg>
              )}
            </a>
          ))}
        </div>

        <div 
          style={{
            width: '1px',
            height: '20px',
            background: 'var(--ifm-color-emphasis-300)',
            margin: '0 0.25rem'
          }}
        ></div>

        {/* Theme toggle button (use Docusaurus v2 colorMode) */}
        <button
          aria-label="Toggle theme"
          onClick={() => setColorMode(colorMode === "dark" ? "light" : "dark")}
          className="lf-navbar-theme-toggle"
        >
          {colorMode === "dark" ? (
            <Icon name="Moon" size={18} />
          ) : (
            <Icon name="Sun" size={18} />
          )}
        </button>
      </div>
    </nav>
  );
}
