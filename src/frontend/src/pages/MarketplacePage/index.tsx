import { useState } from "react";

import Fuse from "fuse.js";
import Select from "react-select";
import IconComponent from "../../components/genericIconComponent";
import Header from "../../components/headerComponent";
import InputComponent from "../../components/inputComponent";
import { MarketCardComponent } from "../../components/marketCardComponent";
import data from "./data.json";
export default function MarketplacePage() {
  const [filteredTags, setFilteredTags] = useState([]);
  const [filteredCategories, setFilteredCategories] = useState([]);
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

  const handleChangeCategories = (e) => {
    setFilteredCategories(e);
  };

  const handleChangeTags = (e) => {
    setFilteredTags(e);
  };
  console.log(filteredCategories);

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
          <div className="flex items-center justify-between">
            <div className="flex w-96 items-center gap-4">
              <InputComponent
                icon="Search"
                placeholder="Search Components"
                onChange={(e) => searchItem(e)}
                value=""
                password={false}
              />
            </div>
            <div className="flex items-center gap-4">
              <div className="w-72">
                <Select
                  isMulti
                  value={filteredCategories}
                  onChange={handleChangeCategories}
                  placeholder="Filter by category"
                  className="text-sm"
                  options={
                    searchData
                      ? Array.from(
                          new Set(
                            searchData.map((item) => ({
                              value: item.category,
                              label: item.category,
                            }))
                          )
                        )
                      : []
                  }
                />
              </div>
              <div className="w-72">
                <Select
                  isMulti
                  placeholder="Filter by tags"
                  value={filteredTags}
                  onChange={handleChangeTags}
                  className="text-sm"
                  options={
                    searchData
                      ? Array.from(
                          new Set(searchData.map((item) => item.tags).flat())
                        ).map((item) => ({ value: item, label: item }))
                      : []
                  }
                />
              </div>
            </div>
          </div>
          <div className="community-pages-flows-panel">
            {searchData
              .filter(
                (f) =>
                  filteredTags.length === 0 ||
                  filteredTags
                    .map((x) => x.value)
                    .every((x) => f.tags.includes(x))
              )
              .filter(
                (f) =>
                  filteredCategories.length === 0 ||
                  filteredCategories.map((x) => x.value).includes(f.category)
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
