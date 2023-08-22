import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

export const CatchAllRoute = () => {
  const navigate = useNavigate();

  // Redirect to the root ("/") when the catch-all route is matched
  useEffect(() => {
    navigate("/");
  }, []);

  return null;
};
