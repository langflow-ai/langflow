import { useState } from "react";

import Fuse from "fuse.js";
import { cloneDeep } from "lodash";
import IconComponent from "../../components/genericIconComponent";
import Header from "../../components/headerComponent";
import InputComponent from "../../components/inputComponent";
import { MarketCardComponent } from "../../components/marketCardComponent";
import { MarketCardComponentComponent } from "../../components/marketCardComponentComponent";
import { Badge } from "../../components/ui/badge";
import { classNames } from "../../utils/utils";
import data from "./data.json";

export default function MarketplacePage() {
  const [filteredCategories, setFilteredCategories] = useState(new Set());
  const [inputText, setInputText] = useState("");
  const [searchData, setSearchData] = useState(data);
  const searchItem = (query) => {
    setInputText(query);
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
            <div className="w-[35%]">
              <InputComponent
                big
                icon="Search"
                placeholder="Search Flows and Components"
                onChange={(e) => searchItem(e)}
                value={inputText}
                password={false}
              />
            </div>
          </div>
          <div className="flex items-center justify-center gap-4">
            {Array.from(new Set(searchData.map((i) => i.type))).map(
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
                  variant="gray"
                  size="md"
                  className={classNames(
                    "cursor-pointer border-none",
                    filteredCategories.has(i)
                      ? "bg-beta-foreground text-background hover:bg-beta-foreground"
                      : ""
                  )}
                >
                  <IconComponent name={i} className="mr-1.5 w-4" />
                  {i}
                </Badge>
              )
            )}
          </div>
          <div className="community-pages-flows-panel mt-6">
            {searchData
              .filter(
                (f) =>
                  Array.from(filteredCategories).length === 0 ||
                  filteredCategories.has(f.type)
              )
              .map((item, idx) => (
                <MarketCardComponent key={idx} data={item} onAdd={() => {}} />
              ))}
            {searchData
              .filter(
                (f) =>
                  Array.from(filteredCategories).length === 0 ||
                  filteredCategories.has(f.type)
              )
              .map((item, idx) => (
                <MarketCardComponentComponent
                  key={idx}
                  data={item}
                  onAdd={() => {}}
                />
              ))}
          </div>
        </div>
      </div>
    </>
  );
}
