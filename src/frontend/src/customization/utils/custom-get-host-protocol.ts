export const customGetHostProtocol = () => {
  return {
    host: window.location.host,
    protocol: window.location.protocol,
  };
};
