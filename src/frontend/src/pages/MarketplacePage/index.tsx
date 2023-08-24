import { useState } from "react";

import Fuse from "fuse.js";
import { cloneDeep } from "lodash";
import tinycolor from "tinycolor2";
import IconComponent from "../../components/genericIconComponent";
import Header from "../../components/headerComponent";
import InputComponent from "../../components/inputComponent";
import { MarketCardComponent } from "../../components/marketCardComponent";
import { Badge } from "../../components/ui/badge";
import { nodeColors, nodeNames } from "../../utils/styleUtils";
import data from "./data.json";

export default function MarketplacePage() {
  const [filteredCategories, setFilteredCategories] = useState(new Set());
  const [searchData, setSearchData] = useState(data);
  const searchItem = (query) => {
    if (!query) {
      setSearchData(data);
      return;
    }
    const fuse = new Fuse(data, {
      keys: ["name", "description", "category", "creator"],
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
          <div className="flex items-center justify-center gap-4">
            <div className="w-[45%]">
              <InputComponent
                icon="Search"
                placeholder="Search Components"
                onChange={(e) => searchItem(e)}
                value=""
                password={false}
              />
            </div>
          </div>
          <div className="flex items-center justify-center gap-4">
            {Array.from(new Set(searchData.map((i) => i.category))).map(
              (i, idx) => (
                <Badge
                  onClick={() => {
                    filteredCategories.has(i)
                      ? setFilteredCategories((old) => {
                          let newFilteredCategories = cloneDeep(old);
                          newFilteredCategories.delete(i);
                          return newFilteredCategories;
                        })
                      : setFilteredCategories((old) => {
                          let newFilteredCategories = cloneDeep(old);
                          newFilteredCategories.add(i);
                          return newFilteredCategories;
                        });
                  }}
                  size="md"
                  variant="inherit"
                  className="cursor-pointer"
                  style={{
                    color: filteredCategories.has(i)
                      ? tinycolor(nodeColors[i]).lighten(50).toString()
                      : tinycolor(nodeColors[i]).darken(20).toString(),
                    backgroundColor: !filteredCategories.has(i)
                      ? tinycolor(nodeColors[i]).lighten(38).toString()
                      : nodeColors[i],
                  }}
                >
                  {nodeNames[i]}
                </Badge>
              )
            )}
          </div>
          <div className="community-pages-flows-panel mt-6">
            {searchData
              .filter(
                (f) =>
                  Array.from(filteredCategories).length === 0 ||
                  filteredCategories.has(f.category)
              )
              .map((item, idx) => (
                <MarketCardComponent key={idx} data={item} onAdd={() => {}} />
              ))}
          </div>
        </div>
      </div>
    </>
  );
}
