export default function tabsArray(codes: string[], method: number) {
  if (!method) return;
  if (method === 0) {
    return [
      {
        name: "cURL",
        mode: "bash",
        image: "https://curl.se/logo/curl-symbol-transparent.png",
        language: "sh",
        code: codes[0],
      },
      {
        name: "Python API",
        mode: "python",
        image:
          "https://images.squarespace-cdn.com/content/v1/5df3d8c5d2be5962e4f87890/1628015119369-OY4TV3XJJ53ECO0W2OLQ/Python+API+Training+Logo.png?format=1000w",
        language: "py",
        code: codes[1],
      },
      {
        name: "Python Code",
        mode: "python",
        image: "https://cdn-icons-png.flaticon.com/512/5968/5968350.png",
        language: "py",
        code: codes[2],
      },
      {
        name: "Chat Widget HTML",
        description:
          "Insert this code anywhere in your &lt;body&gt; tag. To use with react and other libs, check our <a class='link-color' href='https://langflow.org/guidelines/widget'>documentation</a>.",
        mode: "html",
        image: "https://cdn-icons-png.flaticon.com/512/5968/5968350.png",
        language: "py",
        code: codes[3],
      },
    ];
  }
  return [
    {
      name: "cURL",
      mode: "bash",
      image: "https://curl.se/logo/curl-symbol-transparent.png",
      language: "sh",
      code: codes[0],
    },
    {
      name: "Python API",
      mode: "python",
      image:
        "https://images.squarespace-cdn.com/content/v1/5df3d8c5d2be5962e4f87890/1628015119369-OY4TV3XJJ53ECO0W2OLQ/Python+API+Training+Logo.png?format=1000w",
      language: "py",
      code: codes[1],
    },
    {
      name: "Python Code",
      mode: "python",
      language: "py",
      image: "https://cdn-icons-png.flaticon.com/512/5968/5968350.png",
      code: codes[2],
    },
    {
      name: "Chat Widget HTML",
      description:
        "Insert this code anywhere in your &lt;body&gt; tag. To use with react and other libs, check our <a class='link-color' href='https://langflow.org/guidelines/widget'>documentation</a>.",
      mode: "html",
      image: "https://cdn-icons-png.flaticon.com/512/5968/5968350.png",
      language: "py",
      code: codes[3],
    },
    {
      name: "Tweaks",
      mode: "python",
      image: "https://cdn-icons-png.flaticon.com/512/5968/5968350.png",
      language: "py",
      code: codes[4],
    },
  ];
}
