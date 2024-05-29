Cypress.on("uncaught:exception", (err, runnable) => {
  return false;
});

describe("select and delete all", () => {
  it("should select and delete all items", () => {
    cy.visit("http://localhost:3000/");
    cy.wait(2000);

    cy.contains("New Project").click();

    cy.findByText("Basic Prompting (Hello, World)").click();
    cy.get("[data-testid='icon-ChevronLeft']").first().click();

    cy.contains("Select All").click();
    cy.contains("Unselect All").should("be.visible");
    cy.get("[data-testid='icon-Trash2']").click();
    cy.get('button:contains("Delete")').click();

    cy.wait(1000);
    cy.contains("Selected items deleted successfully").should("be.visible");
  });
});

describe("search flows", () => {
  it("should perform search flows", () => {
    cy.visit("http://localhost:3000/");
    cy.wait(2000);

    cy.contains("New Project").click();

    cy.findByText("Basic Prompting (Hello, World)").click();
    cy.get("[data-testid='icon-ChevronLeft']").first().click();

    cy.contains("Select All").should("be.visible");
    cy.contains("New Project").click();
    cy.findByText("Memory Chatbot").click();
    cy.get("[data-testid='icon-ChevronLeft']").first().click();
    cy.contains("New Project").click();
    cy.findByText("Document QA").click();
    cy.get("[data-testid='icon-ChevronLeft']").first().click();
    cy.get("[placeholder='Search Flows and Components']").type(
      "Memory Chatbot",
    );
    cy.contains("Memory Chatbot").should("be.visible");
    cy.contains("Document QA").should("not.exist");
    cy.contains("Basic Prompting").should("not.exist");
  });
});

describe("search components", () => {
  it("should perform search components", () => {
    cy.visit("http://localhost:3000/");
    cy.wait(2000);
    cy.contains("New Project").click();

    cy.findByText("Basic Prompting (Hello, World)").click();

    cy.findByText("Chat Input").first().click();
    cy.get("[data-testid='icon-SaveAll']").first().click();
    cy.focused().type("{esc}");
    cy.findByText("Prompt").first().click();
    cy.get("[data-testid='icon-SaveAll']").first().click();
    cy.focused().type("{esc}");
    cy.findByText("OpenAI").first().click();
    cy.get("[data-testid='icon-SaveAll']").first().click();
    cy.focused().type("{esc}");
    cy.get("[data-testid='icon-ChevronLeft']").first().click();

    cy.findByText("Components").click();

    cy.get("[placeholder='Search Components']").type("Chat Input");
    cy.contains("Chat Input").should("be.visible");
    cy.contains("Prompt").should("not.exist");
    cy.contains("OpenAI").should("not.exist");
  });
});
