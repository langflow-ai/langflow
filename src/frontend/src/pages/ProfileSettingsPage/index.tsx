import { useContext, useEffect } from "react";
import IconComponent from "../../components/genericIconComponent";
import Header from "../../components/headerComponent";
import { Input } from "../../components/ui/input";
import { alertContext } from "../../contexts/alertContext";
import { TabsContext } from "../../contexts/tabsContext";
export default function ProfileSettingsPage(): JSX.Element {
  const { setTabId } = useContext(TabsContext);

  // set null id
  useEffect(() => {
    setTabId("");
  }, []);
  const { setErrorData } = useContext(alertContext);

  return (
    <>
      <Header />

      <div className="community-page-arrangement">
        <div className="community-page-nav-arrangement">
          <span className="community-page-nav-title">
            <IconComponent name="User" className="w-6" />
            Profile Settings
          </span>
        </div>
        <span className="community-page-description-text">
          Change your profile settings like your password and your profile
          picture.
        </span>
        <div className="community-pages-flows-panel">
          <Input placeholder="Password"></Input>
        </div>
      </div>
    </>
  );
}
