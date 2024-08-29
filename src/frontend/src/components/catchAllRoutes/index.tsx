import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { useEffect } from "react";

export const CatchAllRoute = () => {
  const navigate = useCustomNavigate();

  // Redirect to the root ("/") when the catch-all route is matched
  useEffect(() => {
    navigate("/");
  }, []);

  return null;
};
