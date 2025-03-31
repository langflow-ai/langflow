// By default, the classic theme does not provide any SearchBar implementation
// If you swizzled this, it is your responsibility to provide an implementation
// Tip: swizzle the SearchBar from the Algolia theme for inspiration:
// npm run swizzle @docusaurus/theme-search-algolia SearchBar
import React from 'react'
import { MendableSearchBar } from '@mendable/search'
import useDocusaurusContext from '@docusaurus/useDocusaurusContext'

export default function SearchBarWrapper() {
  const {
    siteConfig: { customFields },
  } = useDocusaurusContext()
  return (
    <div className="mendable-search">
      <MendableSearchBar
        anon_key={customFields.mendableAnonKey}
        placeholder="Search..."
        dialogPlaceholder="How to deploy my application?"
        showSimpleSearch
      />
    </div>
  )
}
