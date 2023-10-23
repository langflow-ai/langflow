import { cloneDeep } from "lodash";
import { Link, Search } from "lucide-react";
import { useContext, useEffect, useState } from "react";
import IconComponent from "../../components/genericIconComponent";
import Header from "../../components/headerComponent";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import { Switch } from "../../components/ui/switch";
import { alertContext } from "../../contexts/alertContext";
import { AuthContext } from "../../contexts/authContext";
import { TabsContext } from "../../contexts/tabsContext";
import { getStoreComponents, searchComponent } from "../../controllers/API";
import StoreApiKeyModal from "../../modals/StoreApiKeyModal";
import { FlowComponent } from "../../types/store";
import { cn } from "../../utils/utils";
import { MarketCardComponent } from "./components/market-card";
export default function StorePage(): JSX.Element {
  const { setTabId } = useContext(TabsContext);

  const { setApiKey, apiKey } = useContext(AuthContext);

  // set null id
  useEffect(() => {
    setTabId("");
  }, []);
  const [data, setData] = useState<FlowComponent[]>([]);
  const [dataSelect, setDataSelect] = useState<FlowComponent[]>([]);
  const [loading, setLoading] = useState(false);
  const [filteredCategories, setFilteredCategories] = useState(new Set());
  const [inputText, setInputText] = useState<string>("");
  const [searchData, setSearchData] = useState(data);
  const { setErrorData } = useContext(alertContext);

  useEffect(() => {
    handleGetComponents();
  }, []);

  const handleGetComponents = () => {
    setLoading(true);
    getStoreComponents(1, 10)
      .then((res) => {
        console.log(res);
        setLoading(false);
      })
      .catch((err) => {
        setLoading(false);
        setErrorData({
          title: "Error to get components.",
          list: [err["response"]["data"]["detail"]],
        });
      });
  };

  const handleSearch = (inputText: string) => {
    searchComponent(inputText).then(
      (res) => {
        console.log(res);
      },
      (error) => {}
    );
  };

  return (
    <>
      <Header />

      <div className="community-page-arrangement">
        <div className="community-page-nav-arrangement">
          <span className="community-page-nav-title">
            <IconComponent name="Users2" className="w-6" />
            Langflow Store
          </span>
          <div className="community-page-nav-button">
            <StoreApiKeyModal
              onCloseModal={() => {
                handleGetComponents();
              }}
            >
              <Button variant="primary">
                <IconComponent name="Key" className="main-page-nav-button" />
                API Key
              </Button>
            </StoreApiKeyModal>
          </div>
        </div>
        <span className="community-page-description-text">
          Search flows and components from the community.
        </span>
        {!loading && apiKey && (
          <div className="flex w-full flex-col gap-4 p-4">
            <div className="flex items-center justify-center gap-4">
              <div className="flex w-[13%] items-center justify-center gap-3 text-sm">
                Installed Only <Switch />
              </div>
              <div className="relative h-12 w-[35%]">
                <Input
                  placeholder="Search Flows and Components"
                  className="absolute h-12 px-5"
                  onChange={(e) => {
                    setInputText(e.target.value);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      handleSearch(inputText);
                    }
                  }}
                  value={inputText}
                />
                <Search className="absolute bottom-0 right-4 top-0 my-auto h-6 stroke-1 text-muted-foreground " />
              </div>
              <div className="flex items-center justify-center text-sm">
                <Button
                  onClick={() => {
                    handleSearch(inputText);
                  }}
                >
                  Search
                </Button>
              </div>
              <div className="flex w-[13%] items-center justify-center gap-3 text-sm">
                <Select
                  onValueChange={(value) => {
                    const filter = value === "Flow" ? false : true;
                    const search = data.filter(
                      (f) => f.is_component === filter
                    );
                    value === "" ? setSearchData(data) : setSearchData(search);
                  }}
                >
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Flows" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Flow">Flows</SelectItem>
                    <SelectItem value="Component">Components</SelectItem>
                    <SelectItem value="">Both</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex items-center justify-center gap-4">
              {Array.from(new Set(searchData.map((i) => i.is_component))).map(
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
                    className={cn(
                      "cursor-pointer border-none",
                      filteredCategories.has(i)
                        ? "bg-beta-foreground text-background hover:bg-beta-foreground"
                        : ""
                    )}
                  >
                    <Link className="mr-1.5 w-4" />
                    {i}
                  </Badge>
                )
              )}
            </div>
            <div className="mt-6 grid w-full gap-4 md:grid-cols-2 lg:grid-cols-3">
              {searchData
                .filter(
                  (f) =>
                    Array.from(filteredCategories).length === 0 ||
                    filteredCategories.has(f.is_component)
                )
                .map((item, idx) => (
                  <MarketCardComponent key={idx} data={item} onAdd={() => {}} />
                ))}
            </div>
          </div>
        )}

        {!apiKey && (
          <div className="flex w-full flex-col gap-4 p-4">
            Try add an API Key :)
          </div>
        )}

        {apiKey && loading && (
          <div className="flex w-full flex-col gap-4 p-4">Loading...</div>
        )}
      </div>
    </>
  );
}
