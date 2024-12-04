import { expect, Page, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { addNewApiKeys } from "../../utils/add-new-api-keys";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { removeOldApiKeys } from "../../utils/remove-old-api-keys";
import { selectGptModel } from "../../utils/select-gpt-model";
import { updateOldComponents } from "../../utils/update-old-components";

test(
  "Travel Planning Agent",
  { tag: ["@release", "@starter-project"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    test.skip(
      !process?.env?.SEARCH_API_KEY,
      "SEARCH_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await page.goto("/");
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: "Travel Planning Agents" })
      .last()
      .click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await initialGPTsetup(page);

    const randomCity = cities[Math.floor(Math.random() * cities.length)];
    const randomCity2 = cities[Math.floor(Math.random() * cities.length)];
    const randomFood = foods[Math.floor(Math.random() * foods.length)];

    await page
      .getByTestId("textarea_str_input_value")
      .first()
      .fill(
        `Create a travel plan from ${randomCity} to ${randomCity2} with ${randomFood}`,
      );

    await page
      .getByTestId("popover-anchor-input-api_key")
      .first()
      .fill(process.env.SEARCH_API_KEY ?? "");

    await page.waitForTimeout(1000);

    await page.getByTestId("button_run_chat output").click();

    await page.getByTestId("button_run_chat output").last().click();

    if (await checkRateLimit(page)) {
      console.log("Rate limit detected, skipping test");
      test.skip();
    }

    await page.waitForSelector("text=built successfully", {
      timeout: 60000 * 3,
    });

    await page.getByText("built successfully").last().click({
      timeout: 15000,
    });

    await page.getByText("Playground", { exact: true }).last().click();

    await page.waitForSelector("text=default session", {
      timeout: 30000,
    });

    await page.waitForTimeout(1000);

    const output = await page.getByTestId("div-chat-message").allTextContents();
    const outputText = output.join("\n");

    expect(outputText.toLowerCase()).toContain("weather");
    expect(outputText.toLowerCase()).toContain("budget");

    expect(outputText.toLowerCase()).toContain(randomCity.toLowerCase());
    expect(outputText.toLowerCase()).toContain(randomCity2.toLowerCase());
    expect(outputText.toLowerCase()).toContain(randomFood.toLowerCase());
  },
);

async function checkRateLimit(page: Page): Promise<boolean> {
  try {
    await Promise.race([
      page.waitForSelector("text=429", { timeout: 10000 }),
      page.waitForSelector("text=Too Many Requests", { timeout: 10000 }),
      page.waitForResponse((response) => response.status() === 429, {
        timeout: 10000,
      }),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error("No rate limit detected")), 10000),
      ),
    ]);
    return true;
  } catch {
    return false;
  }
}

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
