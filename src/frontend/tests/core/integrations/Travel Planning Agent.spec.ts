import { expect } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { configureLoopbackOpenAI } from "../../utils/configure-loopback-openai";
import { configureLoopbackWebSearch } from "../../utils/configure-loopback-web-search";
import { TEXTS } from "../../utils/constants/texts";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { seedLoopbackProvider } from "../../utils/seed-loopback-provider";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Travel Planning Agent",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    await seedLoopbackProvider(page);
    await page.goto("/");
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: "Travel Planning Agents" })
      .last()
      .click();

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await configureLoopbackOpenAI(page);
    await configureLoopbackWebSearch(page);

    const randomCity = cities[Math.floor(Math.random() * cities.length)];
    const randomCity2 = cities[Math.floor(Math.random() * cities.length)];
    const randomFood = foods[Math.floor(Math.random() * foods.length)];

    const flowId = new URL(page.url()).pathname.match(/\/flow\/([^/]+)/)?.[1];
    expect(flowId).toBeTruthy();
    const inputSave = page.waitForResponse(
      (candidate) =>
        candidate.request().method() === "PATCH" &&
        new URL(candidate.url()).pathname === `/api/v1/flows/${flowId}`,
      { timeout: TIMEOUTS.standard },
    );
    await page
      .getByTestId("textarea_str_input_value")
      .first()
      .fill(
        `Create a travel plan from ${randomCity} to ${randomCity2} with ${randomFood}`,
      );
    const inputSaveResponse = await inputSave;
    expect(inputSaveResponse.ok()).toBeTruthy();

    const runButton = page.getByTestId("button_run_chat output");
    await expect(runButton).toBeVisible();
    const [response] = await Promise.all([
      page.waitForResponse(
        (candidate) =>
          candidate.request().method() === "POST" &&
          new URL(candidate.url()).pathname === "/api/v2/workflows",
      ),
      runButton.click(),
    ]);
    expect(response.ok()).toBeTruthy();
    expect(await response.finished()).toBeNull();

    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();

    await page.waitForSelector("text=default session", {
      timeout: 30000,
    });

    const output = await page.getByTestId("div-chat-message").allTextContents();
    const outputText = output.join("\n");

    expect(outputText.toLowerCase()).toContain("travel");
    expect(outputText.toLowerCase()).toContain("day");
    expect(outputText).toContain("LOOPBACK_WEB_SEARCH_USED");

    expect(outputText.toLowerCase()).toContain(randomCity.toLowerCase());
    expect(outputText.toLowerCase()).toContain(randomCity2.toLowerCase());
    expect(outputText.toLowerCase()).toContain(randomFood.toLowerCase());
  },
);

const cities = [
  "Tokyo",
  "New York",
  "London",
  "Paris",
  "Singapore",
  "Dubai",
  "Shanghai",
  "Sydney",
  "Mumbai",
  "Madrid",
  "Rome",
  "Berlin",
  "Moscow",
  "Toronto",
  "Chicago",
  "Amsterdam",
  "Bangkok",
  "Seoul",
  "Istanbul",
  "Vienna",
  "Prague",
  "Lisbon",
  "Dublin",
  "Copenhagen",
  "Stockholm",
  "Oslo",
  "Helsinki",
  "Athens",
  "Budapest",
  "Warsaw",
  "Brussels",
  "Barcelona",
  "Milan",
  "Munich",
  "Vancouver",
  "Montreal",
  "Boston",
  "Miami",
  "San Francisco",
  "Seattle",
  "Portland",
  "Austin",
  "Denver",
  "Nashville",
  "New Orleans",
  "Las Vegas",
  "Cairo",
  "Cape Town",
  "Marrakech",
  "Nairobi",
  "Lagos",
  "Johannesburg",
  "Casablanca",
  "Rio de Janeiro",
  "Buenos Aires",
  "São Paulo",
  "Lima",
  "Bogotá",
  "Santiago",
  "Mexico City",
  "Havana",
  "San Juan",
  "Panama City",
  "Quito",
  "Kuala Lumpur",
  "Jakarta",
  "Manila",
  "Hong Kong",
  "Taipei",
  "Osaka",
  "Kyoto",
  "Beijing",
  "Delhi",
  "Bangalore",
  "Chennai",
  "Kolkata",
  "Dubai",
  "Abu Dhabi",
  "Doha",
  "Kuwait City",
  "Tel Aviv",
  "Jerusalem",
  "Damascus",
  "Beirut",
  "Tehran",
  "Baghdad",
  "Riyadh",
  "Muscat",
  "Manama",
  "Amman",
  "Edinburgh",
  "Manchester",
  "Liverpool",
  "Birmingham",
  "Bristol",
  "Cambridge",
  "Oxford",
  "Cardiff",
  "Belfast",
  "Glasgow",
];

const foods = [
  "Sushi",
  "Pizza",
  "Paella",
  "Curry",
  "Tacos",
  "Pad Thai",
  "Hamburger",
  "Croissant",
  "Ramen",
  "Dim Sum",
  "Pasta Carbonara",
  "Biryani",
  "Fish and Chips",
  "Pho",
  "Peking Duck",
  "Lasagna",
  "Moussaka",
  "Butter Chicken",
  "Falafel",
  "Schnitzel",
  "Goulash",
  "Sushi Roll",
  "Enchiladas",
  "Pierogi",
  "Coq au Vin",
  "Tandoori Chicken",
  "Risotto",
  "Gyros",
  "Tempura",
  "Tom Yum",
  "Beef Stroganoff",
  "Kimchi",
  "Ceviche",
  "Gnocchi",
  "Poutine",
  "Chow Mein",
  "Shepherd's Pie",
  "Mole Poblano",
  "Borscht",
  "Gazpacho",
  "Bibimbap",
  "Chicken Tikka Masala",
  "Pastrami",
  "Jambalaya",
  "Sashimi",
  "Bratwurst",
  "Osso Buco",
  "Bouillabaisse",
  "Nasi Goreng",
  "Tiramisu",
  "Kung Pao Chicken",
  "Eggs Benedict",
  "Beef Wellington",
  "Lobster Thermidor",
  "Duck Confit",
  "Escargot",
  "Chicken Satay",
  "Tom Kha Gai",
  "Beef Rendang",
  "Shakshuka",
  "Cachapa",
  "Empanada",
  "Poke Bowl",
  "Baklava",
  "Spanakopita",
  "Etouffee",
  "Cassoulet",
  "Ratatouille",
  "Quiche Lorraine",
  "Couscous",
  "Miso Soup",
  "Gumbo",
  "Chicken Parmesan",
  "Ravioli",
  "Beef Bourguignon",
  "Thai Green Curry",
  "Soba Noodles",
  "Kebab",
  "Baba Ganoush",
  "Hummus",
  "Churros",
  "Crepes",
  "Wonton Soup",
  "Dumplings",
  "Spring Rolls",
  "Samosas",
  "Tortilla Española",
  "Croquetas",
  "Greek Salad",
  "Boeuf Bourguignon",
  "Pavlova",
  "Beef Tartare",
  "Stuffed Grape Leaves",
  "Parmigiana",
  "Cacio e Pepe",
  "Bulgogi",
  "Hot Pot",
  "Sukiyaki",
  "Chicken Adobo",
  "Laksa",
];
