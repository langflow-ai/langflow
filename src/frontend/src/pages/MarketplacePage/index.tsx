import { useState } from "react";

import Fuse from "fuse.js";
import IconComponent from "../../components/genericIconComponent";
import Header from "../../components/headerComponent";
import InputComponent from "../../components/inputComponent";
import { MarketCardComponent } from "../../components/marketCardComponent";
import data from "./data.json";
export default function MarketplacePage() {
  const [searchData, setSearchData] = useState(data);
  const searchItem = (query) => {
    if (!query) {
      setSearchData(data);
      return;
    }
    const fuse = new Fuse(data, {
      keys: ["name", "description"],
    });
    const result = fuse.search(query);
    const finalResult = [];
    if (result.length) {
      result.forEach((item) => {
        finalResult.push(item.item);
      });
      setSearchData(finalResult);
    } else {
      setSearchData([]);
    }
  };

  return (
    <>
      <Header />

      <div className="community-page-arrangement">
        <div className="community-page-nav-arrangement">
          <span className="community-page-nav-title">
            <IconComponent name="Users2" className="w-6" />
            Components
          </span>
        </div>
        <span className="community-page-description-text">
          Discover and learn from shared components by the Langflow community.
          We welcome new component contributions that can help our community
          explore new and powerful features.
        </span>
        <div className="flex w-full flex-col gap-4 p-4">
          <div className="flex justify-between">
            <div className="flex w-96 items-center gap-4">
              <InputComponent
                icon="Search"
                placeholder="Search Components"
                onChange={(e) => searchItem(e)}
                value=""
                password={false}
              />
            </div>
          </div>
          <div className="community-pages-flows-panel">
            {searchData.map((item, idx) => (
              <MarketCardComponent key={idx} data={item} onAdd={() => {}} />
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
