import { Group, ToyBrick } from "lucide-react";
import { useContext, useEffect } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import DropdownButton from "../../components/DropdownButtonComponent";
import IconComponent from "../../components/genericIconComponent";
import PageLayout from "../../components/pageLayout";
import SidebarNav from "../../components/sidebarComponent";
import { Button } from "../../components/ui/button";
import { USER_PROJECTS_HEADER } from "../../constants/constants";
import { alertContext } from "../../contexts/alertContext";
import { FlowsContext } from "../../contexts/flowsContext";
export default function HomePage(): JSX.Element {
  const { setTabId, downloadFlows, uploadFlows, addFlow, uploadFlow } =
    useContext(FlowsContext);
  const { setErrorData, setSuccessData } = useContext(alertContext);
  const location = useLocation();
  const pathname = location.pathname;
  const is_component = pathname === "/components";
  const dropdownOptions = [
    {
      name: "Import from JSON",
      onBtnClick: () => {
        uploadFlow({
          newProject: true,
          isComponent: is_component,
        })
          .then((id) => {
            setSuccessData({
              title: `${
                is_component ? "Component" : "Flow"
              } uploaded successfully`,
            });
            if (!is_component) navigate("/flow/" + id);
          })
          .catch((error) => {
            setErrorData({
              title: "Error uploading file",
              list: [error],
            });
          });
      },
    },
  ];
  const sidebarNavItems = [
    {
      title: "Flows",
      href: "/flows",
      icon: <Group className="w-5 stroke-[1.5]" />,
    },
    {
      title: "Components",
      href: "/components",
      icon: <ToyBrick className="mx-[0.08rem] w-[1.1rem] stroke-[1.5]" />,
    },
  ];

  // Set a null id
  useEffect(() => {
    setTabId("");
  }, [pathname]);

  const navigate = useNavigate();

  // Personal flows display
  return (
    <PageLayout
      title={USER_PROJECTS_HEADER}
      description="Manage your personal projects. Download or upload your collection."
      button={
        <div className="flex gap-2">
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
      }
    >
      <div className="flex h-full w-full space-y-8 lg:flex-row lg:space-x-8 lg:space-y-0">
        <aside className="flex h-full flex-col space-y-6 lg:w-1/5">
          <SidebarNav items={sidebarNavItems} />
        </aside>
        <div className="h-full w-full flex-1">
          <Outlet />
        </div>
      </div>
    </PageLayout>
  );
}
