import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to interact with sticky notes",
  { tag: ["@release", "@workspace"] },

  async ({ page }) => {
    const randomTitle = Math.random()
      .toString(36)
      .substring(7)
      .padEnd(8, "x")
      .substring(0, 8);

    const noteText = `# ${randomTitle}

Artificial Intelligence (AI) has rapidly evolved from a speculative concept in science fiction to a transformative force reshaping industries and everyday life. The term AI encompasses a broad range of technologies, from simple algorithms designed to perform specific tasks to complex systems capable of learning and adapting independently. As AI continues to advance, its applications are becoming increasingly diverse, impacting everything from healthcare to finance, entertainment, and beyond.

At its core, AI is about creating systems that can perform tasks that would typically require human intelligence. This includes abilities such as visual perception, speech recognition, decision-making, and even language translation. The development of AI can be traced back to the mid-20th century, when pioneers like Alan Turing began exploring the idea of machines that could think. Turing's famous "Turing Test" proposed a benchmark for AI, where a machine would be considered intelligent if it could engage in a conversation with a human without being detected as a machine.

The early days of AI research were marked by optimism, with researchers believing that human-like intelligence in machines was just around the corner. However, progress was slower than expected, leading to periods known as "AI winters," where interest and funding in the field waned. Despite these setbacks, AI research persisted, and by the 21st century, significant breakthroughs began to emerge.

One of the key drivers of modern AI is the availability of vast amounts of data. The internet and the proliferation of digital devices have generated unprecedented quantities of data, which AI systems can analyze to identify patterns and make predictions. This data-driven approach is at the heart of machine learning, a subset of AI that focuses on teaching machines to learn from experience rather than relying on explicitly programmed instructions.

Machine learning has enabled remarkable advancements in AI, particularly in areas like image and speech recognition. For example, AI systems can now accurately identify objects in images, transcribe spoken words into text, and even understand natural language. These capabilities have led to the development of virtual assistants like Siri, Alexa, and Google Assistant, which can perform a wide range of tasks, from setting reminders to controlling smart home devices.

Another important development in AI is the rise of deep learning, a type of machine learning that uses artificial neural networks to model complex patterns in data. Deep learning has been instrumental in achieving breakthroughs in areas such as computer vision and natural language processing. For instance, deep learning algorithms power the facial recognition systems used in security applications and the language models behind advanced chatbots and translation services.

AI's impact is not limited to consumer applications; it is also transforming industries on a larger scale. In healthcare, AI is being used to analyze medical images, predict patient outcomes, and even discover new drugs. In finance, AI-driven algorithms are used for trading, fraud detection, and personalized financial advice. The automotive industry is leveraging AI to develop self-driving cars, which have the potential to reduce accidents and revolutionize transportation.

Despite its many benefits, AI also raises important ethical and societal questions. As AI systems become more capable, there are concerns about job displacement, privacy, and the potential for bias in decision-making. AI algorithms are only as good as the data they are trained on, and if that data is biased, the AI's decisions may be biased as well. This has led to calls for greater transparency and accountability in AI development, as well as discussions about the need for regulations to ensure that AI is used responsibly.

The future of AI is both exciting and uncertain. As the technology continues to advance, it will undoubtedly bring about profound changes in society. The challenge will be to harness AI's potential for good while addressing the ethical and societal issues that arise. Whether it's through smarter healthcare, more efficient transportation, or enhanced creativity, AI has the potential to reshape the world in ways we are only beginning to imagine. The journey of AI is far from over, and its impact will be felt for generations to come.
  `;

    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("add_note").click();

    const targetElement = page.locator('//*[@id="react-flow-id"]');
    await targetElement.click();

    await page.mouse.up();
    await page.mouse.down();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    await page.getByTestId("note_node").click();

    await page.locator(".generic-node-desc-text").last().dblclick();
    await page.getByTestId("textarea").fill(noteText);

    expect(await page.getByText("2500/2500")).toBeVisible();

    await targetElement.click();
    const textMarkdown = await page.locator(".markdown").innerText();

    const textLength = textMarkdown.length;
    const noteTextLength = noteText.length;

    expect(textLength).toBeLessThan(noteTextLength);

    await page.getByTestId("note_node").click();

    let element = await page.getByTestId("note_node");

    let hasStyles = await element?.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return (
        style.backgroundColor === "rgb(252, 211, 77)" ||
        style.backgroundColor === "rgb(253, 230, 138)"
      );
    });
    expect(hasStyles).toBe(true);

    await page.getByTestId("note_node").click();

    await page.getByTestId("color_picker").click();

    await page.getByTestId("color_picker_button_rose").click();
    //await for the  animation to complete
    await page.waitForTimeout(1000);

    await page.getByTestId("note_node").click();

    element = await page.getByTestId("note_node");

    hasStyles = await element?.evaluate((el) => {
      const style = window.getComputedStyle(el);

      return (
        style.backgroundColor === "rgb(253, 164, 175)" ||
        style.backgroundColor === "rgb(254, 205, 211)"
      );
    });
    expect(hasStyles).toBe(true);

    await page.getByTestId("note_node").click();
    await page.getByTestId("more-options-modal").click();

    await page.getByText("Duplicate").click();

    let titleNumber = await page.getByText(randomTitle).count();
    expect(titleNumber).toBe(2);

    await page.getByTestId("note_node").last().click();
    await page.getByTestId("more-options-modal").click();

    await page.getByText("Copy").click();

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    //double click
    await targetElement.click();
    await targetElement.click();
    await page.keyboard.press(`ControlOrMeta+v`);

    titleNumber = await page.getByText(randomTitle).count();
    expect(titleNumber).toBe(3);

    await page.getByTestId("note_node").last().click();
    await page.getByTestId("more-options-modal").click();
    await page.getByText("Delete").first().click();

    titleNumber = await page.getByText(randomTitle).count();

    expect(titleNumber).toBe(2);
  },
);
