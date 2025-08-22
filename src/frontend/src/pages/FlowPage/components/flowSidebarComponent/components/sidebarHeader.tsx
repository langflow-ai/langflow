import { memo } from "react";

import { Disclosure, DisclosureContent } from "@/components/ui/disclosure";
import { SidebarHeader } from "@/components/ui/sidebar";
import type { SidebarHeaderComponentProps } from "../types";
import FeatureToggles from "./featureTogglesComponent";
import { SearchInput } from "./searchInput";
import { SidebarFilterComponent } from "./sidebarFilterComponent";

export const SidebarHeaderComponent = memo(function SidebarHeaderComponent({
  showConfig,
  setShowConfig,
  showBeta,
  setShowBeta,
  showLegacy,
  setShowLegacy,
  searchInputRef,
  isInputFocused,
  search,
  handleInputFocus,
  handleInputBlur,
  handleInputChange,
  filterType,
  setFilterEdge,
  setFilterData,
  data,
}: SidebarHeaderComponentProps) {
  return (
    <SidebarHeader className="flex w-full flex-col gap-4 p-4 pb-1 group-data-[collapsible=icon]:hidden">
      <SearchInput
        searchInputRef={searchInputRef}
        isInputFocused={isInputFocused}
        search={search}
        handleInputFocus={handleInputFocus}
        handleInputBlur={handleInputBlur}
        handleInputChange={handleInputChange}
      />
      {filterType && (
        <SidebarFilterComponent
          isInput={!!filterType.source}
          type={filterType.type}
          color={filterType.color}
          resetFilters={() => {
            setFilterEdge([]);
            setFilterData(data);
          }}
        />
      )}
      <Disclosure open={showConfig} onOpenChange={setShowConfig}>
        <DisclosureContent>
          <FeatureToggles
            showBeta={showBeta}
            setShowBeta={setShowBeta}
            showLegacy={showLegacy}
            setShowLegacy={setShowLegacy}
          />
        </DisclosureContent>
      </Disclosure>
    </SidebarHeader>
  );
});

SidebarHeaderComponent.displayName = "SidebarHeaderComponent";
