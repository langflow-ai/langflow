import { useContext, useEffect } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import DropdownButton from "../../components/DropdownButtonComponent";
import IconComponent from "../../components/genericIconComponent";
import Header from "../../components/headerComponent";
import SidebarNav from "../../components/sidebarComponent";
import { Button } from "../../components/ui/button";
import { Separator } from "../../components/ui/separator";
import { USER_PROJECTS_HEADER } from "../../constants/constants";
import { StoreContext } from "../../contexts/storeContext";
import { TabsContext } from "../../contexts/tabsContext";
export default function HomePage(): JSX.Element {
  const { setTabId, downloadFlows, uploadFlows, addFlow, uploadFlow } =
    useContext(TabsContext);
  const { hasStore } = useContext(StoreContext);
  const dropdownOptions = [
    {
      name: "Import from JSON",
      onBtnClick: () =>
        uploadFlow(true).then((id) => {
          navigate("/flow/" + id);
        }),
    },
  ];
  const sidebarNavItems = [
    {
      title: "Flows",
      href: "/flows",
    },
    {
      title: "Components",
      href: "/components",
    },
  ];

  // if (hasStore) {
  //   sidebarNavItems.push({
  //     title: "From Store",
  //     href: "/from-store",
  //   });
  // }

  // Set a null id
  useEffect(() => {
    setTabId("");
  }, []);
  const navigate = useNavigate();

  // Personal flows display
  return (
    <>
      <Header />
      <div className="main-page-panel">
        <div className="main-page-nav-arrangement">
          <span className="main-page-nav-title">
            <IconComponent name="Home" className="w-6" />
            {USER_PROJECTS_HEADER}
          </span>
          <div className="button-div-style">
            <Button
              variant="primary"
              onClick={() => {
                downloadFlows();
              }}
            >
              <IconComponent name="Download" className="main-page-nav-button" />
              Download Collection
            </Button>
            <Button
              variant="primary"
              onClick={() => {
                uploadFlows();
              }}
            >
              <IconComponent name="Upload" className="main-page-nav-button" />
              Upload Collection
            </Button>
            <DropdownButton
              firstButtonName="New Project"
              onFirstBtnClick={() => {
                addFlow(true).then((id) => {
                  navigate("/flow/" + id);
                });
              }}
              options={dropdownOptions}
            />
          </div>
        </div>
        <span className="main-page-description-text">
          Manage your personal projects. Download or upload your collection.
        </span>
        <Separator className="my-6" />
        <div className="flex flex-col space-y-8 lg:flex-row lg:space-x-8 lg:space-y-0">
          <aside className="space-y-6 lg:w-1/5">
            {/* <Input placeholder="Search" onChange={(e) => {}} /> */}
            <SidebarNav
              items={sidebarNavItems}
              secondaryItems={sidebarNavItems}
            />
          </aside>
          <div className="w-full flex-1">
            <Outlet />
          </div>
        </div>
      </div>
    </>
  );
}
