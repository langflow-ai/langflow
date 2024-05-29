const DownloadableJsonFile = ({ source, title }) => {
  const handleDownload = (event) => {
    event.preventDefault();
    fetch(source)
      .then((response) => response.blob())
      .then((blob) => {
        const url = window.URL.createObjectURL(
          new Blob([blob], { type: "application/json" })
        );
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", title);
        document.body.appendChild(link);
        link.click();
        link.parentNode.removeChild(link);
      })
      .catch((error) => {
        console.error("Error downloading file:", error);
      });
  };

  return (
    <a href={source} download={title} onClick={handleDownload}>
      {title}
    </a>
  );
};

export default DownloadableJsonFile;
