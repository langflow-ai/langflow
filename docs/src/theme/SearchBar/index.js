import React, { useCallback, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { DocSearchButton } from "@docsearch/react/button";
import { useDocSearchKeyboardEvents } from "@docsearch/react/useDocSearchKeyboardEvents";
import Head from "@docusaurus/Head";
import Link from "@docusaurus/Link";
import { useHistory } from "@docusaurus/router";
import {
  isRegexpStringMatch,
  useSearchLinkCreator,
} from "@docusaurus/theme-common";
import {
  useAlgoliaContextualFacetFilters,
  useSearchResultUrlProcessor,
  useAlgoliaAskAi,
  mergeFacetFilters,
} from "@docusaurus/theme-search-algolia/client";
import Translate from "@docusaurus/Translate";
import useDocusaurusContext from "@docusaurus/useDocusaurusContext";
import translations from "@theme/SearchTranslations";

let DocSearchModal = null;

function importDocSearchModalIfNeeded() {
  if (DocSearchModal) {
    return Promise.resolve();
  }
  return Promise.all([
    import("@docsearch/react/modal"),
    import("@docsearch/react/style"),
    import("./styles.css"),
  ]).then(([{ DocSearchModal: Modal }]) => {
    DocSearchModal = Modal;
  });
}

function useNavigator({ externalUrlRegex }) {
  const history = useHistory();
  const [navigator] = useState(() => ({
    navigate(params) {
      if (isRegexpStringMatch(externalUrlRegex, params.itemUrl)) {
        window.location.href = params.itemUrl;
      } else {
        history.push(params.itemUrl);
      }
    },
  }));
  return navigator;
}

function useTransformSearchClient() {
  const {
    siteMetadata: { docusaurusVersion },
  } = useDocusaurusContext();
  return useCallback(
    (searchClient) => {
      searchClient.addAlgoliaAgent("docusaurus", docusaurusVersion);
      return searchClient;
    },
    [docusaurusVersion],
  );
}

function useTransformItems(props) {
  const processSearchResultUrl = useSearchResultUrlProcessor();
  const [transformItems] = useState(() => (items) =>
    props.transformItems
      ? props.transformItems(items)
      : items.map((item) => ({ ...item, url: processSearchResultUrl(item.url) })),
  );
  return transformItems;
}

function useResultsFooterComponent({ closeModal }) {
  return useMemo(
    () =>
      ({ state }) =>
        <ResultsFooter state={state} onClose={closeModal} />,
    [closeModal],
  );
}

function Hit({ hit, children }) {
  return <Link to={hit.url}>{children}</Link>;
}

function ResultsFooter({ state, onClose }) {
  const createSearchLink = useSearchLinkCreator();
  return (
    <Link to={createSearchLink(state.query)} onClick={onClose}>
      <Translate id="theme.SearchBar.seeAll" values={{ count: state.context.nbHits }}>
        {"See all {count} results"}
      </Translate>
    </Link>
  );
}

function useSearchParameters({ contextualSearch, ...props }) {
  const contextualSearchFacetFilters = useAlgoliaContextualFacetFilters();
  const configFacetFilters = props.searchParameters?.facetFilters ?? [];
  const facetFilters = contextualSearch
    ? mergeFacetFilters(contextualSearchFacetFilters, configFacetFilters)
    : configFacetFilters;
  return { ...props.searchParameters, facetFilters };
}

function patchDocSearchButtonSvg() {
  if (typeof document === "undefined") return;
  const svgs = document.querySelectorAll(".DocSearch-Button svg");
  svgs.forEach((svg, index) => {
    if (svg.getAttribute("aria-label") || svg.getAttribute("aria-labelledby")) return;
    const existingTitle = svg.querySelector("title");
    if (existingTitle) return;
    const label = index === 0 ? "Option key shortcut icon" : "K key shortcut icon";
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", label);
    svg.setAttribute("focusable", "false");
  });
}

function DocSearch({ externalUrlRegex, ...props }) {
  const navigator = useNavigator({ externalUrlRegex });
  const searchParameters = useSearchParameters({ ...props });
  const transformItems = useTransformItems(props);
  const transformSearchClient = useTransformSearchClient();
  const searchContainer = useRef(null);
  const searchButtonRef = useRef(null);
  const [isOpen, setIsOpen] = useState(false);
  const [initialQuery, setInitialQuery] = useState(undefined);
  const { isAskAiActive, currentPlaceholder, onAskAiToggle, extraAskAiProps } =
    useAlgoliaAskAi(props);

  React.useEffect(() => {
    patchDocSearchButtonSvg();
    const observer = new MutationObserver(() => patchDocSearchButtonSvg());
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [isOpen, currentPlaceholder]);

  const prepareSearchContainer = useCallback(() => {
    if (!searchContainer.current) {
      const divElement = document.createElement("div");
      searchContainer.current = divElement;
      document.body.insertBefore(divElement, document.body.firstChild);
    }
  }, []);

  const openModal = useCallback(() => {
    prepareSearchContainer();
    importDocSearchModalIfNeeded().then(() => setIsOpen(true));
  }, [prepareSearchContainer]);

  const closeModal = useCallback(() => {
    setIsOpen(false);
    searchButtonRef.current?.focus();
    setInitialQuery(undefined);
    onAskAiToggle(false);
  }, [onAskAiToggle]);

  const handleInput = useCallback(
    (event) => {
      if (event.key === "f" && (event.metaKey || event.ctrlKey)) return;
      event.preventDefault();
      setInitialQuery(event.key);
      openModal();
    },
    [openModal],
  );

  const resultsFooterComponent = useResultsFooterComponent({ closeModal });

  useDocSearchKeyboardEvents({
    isOpen,
    onOpen: openModal,
    onClose: closeModal,
    onInput: handleInput,
    searchButtonRef,
    isAskAiActive: isAskAiActive ?? false,
    onAskAiToggle: onAskAiToggle ?? (() => {}),
  });

  return (
    <>
      <Head>
        <link
          rel="preconnect"
          href={`https://${props.appId}-dsn.algolia.net`}
          crossOrigin="anonymous"
        />
      </Head>
      <DocSearchButton
        onTouchStart={importDocSearchModalIfNeeded}
        onFocus={importDocSearchModalIfNeeded}
        onMouseOver={importDocSearchModalIfNeeded}
        onClick={openModal}
        ref={searchButtonRef}
        translations={props.translations?.button ?? translations.button}
      />
      {isOpen &&
        DocSearchModal &&
        searchContainer.current &&
        createPortal(
          <DocSearchModal
            onClose={closeModal}
            initialScrollY={window.scrollY}
            initialQuery={initialQuery}
            navigator={navigator}
            transformItems={transformItems}
            hitComponent={Hit}
            transformSearchClient={transformSearchClient}
            {...(props.searchPagePath && { resultsFooterComponent })}
            placeholder={currentPlaceholder}
            {...props}
            translations={props.translations?.modal ?? translations.modal}
            searchParameters={searchParameters}
            {...extraAskAiProps}
          />,
          searchContainer.current,
        )}
    </>
  );
}

export default function SearchBar() {
  const { siteConfig } = useDocusaurusContext();
  return <DocSearch {...siteConfig.themeConfig.algolia} />;
}
