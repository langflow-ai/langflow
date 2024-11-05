import { tabsArrayType } from "@/types/components";

export function createTabsArray(
  codes: { [key: string]: string },
  includeTweaks = false,
) {
  const tabs: tabsArrayType[] = [];
  if (codes.runCurlCode) {
    tabs.push({
      name: "cURL",
      mode: "bash",
      image: "https://curl.se/logo/curl-symbol-transparent.png",
      language: "sh",
      code: codes.runCurlCode,
      hasTweaks: includeTweaks,
    });
  }
  if (codes.webhookCurlCode) {
    tabs.push({
      name: "Webhook cURL",
      mode: "bash",
      image: "https://curl.se/logo/curl-symbol-transparent.png",
      language: "sh",
      code: codes.webhookCurlCode,
    });
  }
  if (codes.pythonApiCode) {
    tabs.push({
      name: "Python API",
      mode: "python",
      image:
        "https://images.squarespace-cdn.com/content/v1/5df3d8c5d2be5962e4f87890/1628015119369-OY4TV3XJJ53ECO0W2OLQ/Python+API+Training+Logo.png?format=1000w",
      language: "py",
      code: codes.pythonApiCode,
      hasTweaks: includeTweaks,
    });
  }
  if (codes.jsApiCode) {
    tabs.push({
      name: "JS API",
      mode: "javascript",
      image: "https://cdn-icons-png.flaticon.com/512/136/136530.png",
      language: "js",
      code: codes.jsApiCode,
      hasTweaks: includeTweaks,
    });
  }
  if (codes.pythonCode) {
    tabs.push({
      name: "Python Code",
      mode: "python",
      image: "https://cdn-icons-png.flaticon.com/512/5968/5968350.png",
      language: "py",
      code: codes.pythonCode,
      hasTweaks: includeTweaks,
    });
  }
  if (codes.widgetCode) {
    tabs.push({
      name: "Chat Widget HTML",
      description:
        "Insert this code anywhere in your &lt;body&gt; tag. To use with react and other libs, check our <a class='link-color' href='https://langflow.org/guidelines/widget'>documentation</a>.",
      mode: "html",
      image: "https://cdn-icons-png.flaticon.com/512/5968/5968350.png",
      language: "html",
      code: codes.widgetCode,
    });
  }
  if (includeTweaks) {
    tabs.push({
      name: "Tweaks",
      mode: "python",
      image: "https://cdn-icons-png.flaticon.com/512/5968/5968350.png",
      language: "py",
      code: codes.tweaksCode,
    });
  }

  return tabs;
}
