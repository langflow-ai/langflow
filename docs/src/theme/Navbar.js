import React, { useState, useEffect } from "react";
import { useColorMode } from "@docusaurus/theme-common";
import Link from "@docusaurus/Link";
import SearchBar from "@theme/SearchBar";
import ThemedImage from "@theme/ThemedImage";
import { MonitorDown, Moon, Sun } from "lucide-react";
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
            light: "img/lf-docs-light.svg",
            dark: "img/lf-docs-dark.svg",
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
          <MonitorDown size={16} />
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
              <Icon name={link.icon} size={18} />
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
            <Moon size={18} />
          ) : (
            <Sun size={18} />
          )}
        </button>
      </div>
    </nav>
  );
}
