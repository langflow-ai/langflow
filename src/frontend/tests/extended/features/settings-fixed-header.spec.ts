import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { navigateSettingsPages } from "../../utils/go-to-settings";

test(
  "should keep the Settings header and menu in place while the content scrolls",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 600 });
    await awaitBootstrapTest(page, { skipModal: true });

    // The production build bundles ChevronLeft into the main chunk, so only the dev server loads it lazily.
    const backIconIsLazy = process.env.PW_FRONTEND_BUILD !== "1";

    // Hold the lazy Back icon so the header is measured with its loading placeholder.
    let loadBackIcon = () => {};
    const backIconReady = new Promise<void>((resolve) => {
      loadBackIcon = resolve;
    });
    if (backIconIsLazy) {
      await page.route(
        /\/chevron-left(?:-[^/?]+)?\.js(?:\?|$)/,
        async (route) => {
          await backIconReady;
          await route.continue();
        },
      );
    }

    await navigateSettingsPages(page, "Settings", "General");
    await expect(page.getByText("Profile Picture").first()).toBeVisible();

    const title = page.getByTestId("mainpage_title");
    const menuItem = page.getByTestId("sidebar-nav-General");
    const content = page.getByTestId("settings-content-scroll");

    const backButton = page.getByTestId("back_page_button");
    let titleBefore: Awaited<ReturnType<typeof title.boundingBox>>;
    let menuBefore: Awaited<ReturnType<typeof menuItem.boundingBox>>;
    if (backIconIsLazy) {
      await expect(backButton.locator(".animate-pulse")).toBeVisible();
      titleBefore = await title.boundingBox();
      menuBefore = await menuItem.boundingBox();

      loadBackIcon();
      await expect(backButton.getByTestId("icon-ChevronLeft")).toBeVisible();
      expect(await title.boundingBox()).toEqual(titleBefore);
    } else {
      await expect(backButton.getByTestId("icon-ChevronLeft")).toBeVisible();
      titleBefore = await title.boundingBox();
      menuBefore = await menuItem.boundingBox();
    }

    const contentBox = await content.boundingBox();
    await page.mouse.move(
      contentBox!.x + contentBox!.width / 2,
      contentBox!.y + contentBox!.height / 2,
    );
    await page.mouse.wheel(0, 2000);

    await expect
      .poll(() => content.evaluate((element) => element.scrollTop))
      .toBeGreaterThan(0);
    expect(await title.boundingBox()).toEqual(titleBefore);
    expect(await menuItem.boundingBox()).toEqual(menuBefore);
    await expect(
      page.getByRole("button", { name: "Save" }).last(),
    ).toBeInViewport();

    // The scrollbar keeps the page's spacing from the cards instead of touching them.
    const gap = await content.evaluate((scroller) => {
      const box = scroller.getBoundingClientRect();
      const scrollbarLeft =
        box.left + scroller.clientLeft + scroller.clientWidth;
      const cardsRight = (
        scroller.firstElementChild as HTMLElement
      ).getBoundingClientRect().right;
      return scrollbarLeft - cardsRight;
    });
    expect(gap).toBeGreaterThanOrEqual(24);
  },
);
