# Generative UI Examples

This document contains examples of how to use the generative UI feature in Langflow chat playground.

## Simple Button Example

When the AI responds with HTML containing buttons with `data-action` attributes, they become interactive:

```html
<div class="card">
  <h3>Choose an option:</h3>
  <button data-action="button-click" data-value="Yes">Yes</button>
  <button data-action="button-click" data-value="No">No</button>
  <button data-action="button-click" data-value="Maybe">Maybe</button>
</div>
```

## Form Example

Forms can be submitted and their data will be sent as the next chat message:

```html
<div class="card">
  <h3>Contact Information</h3>
  <form>
    <label>Name:</label>
    <input type="text" name="name" placeholder="Your name" />

    <label>Email:</label>
    <input type="email" name="email" placeholder="your@email.com" />

    <label>Message:</label>
    <textarea name="message" placeholder="Your message"></textarea>

    <input type="submit" value="Send Message" />
  </form>
</div>
```

## Interactive Cards Example

Cards with hover effects and click actions:

```html
<div class="grid grid-cols-3 gap-4">
  <div class="card interactive-element">
    <h4>Option 1</h4>
    <p>Description of option 1</p>
    <button data-action="select-option" data-value="Option 1">Select</button>
  </div>
  <div class="card interactive-element">
    <h4>Option 2</h4>
    <p>Description of option 2</p>
    <button data-action="select-option" data-value="Option 2">Select</button>
  </div>
  <div class="card interactive-element">
    <h4>Option 3</h4>
    <p>Description of option 3</p>
    <button data-action="select-option" data-value="Option 3">Select</button>
  </div>
</div>
```

## Alert/Notification Example

```html
<div class="alert alert-info">
  <h4>Information</h4>
  <p>This is an informational message.</p>
  <button data-action="acknowledge" data-value="Info acknowledged">Got it!</button>
</div>

<div class="alert alert-warning">
  <h4>Warning</h4>
  <p>This action cannot be undone.</p>
  <button data-action="confirm-action" data-value="Confirmed">Proceed</button>
  <button data-action="cancel-action" data-value="Cancelled">Cancel</button>
</div>
```

## Table with Action Buttons

```html
<table>
  <thead>
    <tr>
      <th>Item</th>
      <th>Description</th>
      <th>Action</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Item 1</td>
      <td>Description of item 1</td>
      <td><button data-action="select-item" data-value="Item 1">Select</button></td>
    </tr>
    <tr>
      <td>Item 2</td>
      <td>Description of item 2</td>
      <td><button data-action="select-item" data-value="Item 2">Select</button></td>
    </tr>
  </tbody>
</table>
```

## React-like JSX Example

Basic JSX-like syntax (limited support):

```jsx
<>
  <h3>React-like Component</h3>
  <Button onClick="react-button-clicked">Click me!</Button>
  <p>This is a React-like component rendered from JSX.</p>
</>
```

## Navigation Example

Internal navigation links:

```html
<div class="card">
  <h3>Navigation Menu</h3>
  <ul>
    <li><a href="/dashboard" data-action="navigate">Dashboard</a></li>
    <li><a href="/profile" data-action="navigate">Profile</a></li>
    <li><a href="/settings" data-action="navigate">Settings</a></li>
  </ul>
</div>
```

## Usage Notes

1. **Interactive Elements**: Any HTML element with `data-action` attribute becomes interactive
2. **Button Clicks**: Button text or `data-value` is sent as the next chat message
3. **Form Submissions**: Form data is serialized and sent as a structured message
4. **Navigation**: Internal links (not starting with http) trigger navigation events
5. **Styling**: Uses Tailwind CSS classes for styling
6. **Safety**: All HTML is sanitized and rendered safely

## How It Works

1. The AI generates HTML/React content in its response
2. The `GenerativeUIRenderer` detects if content contains interactive elements
3. Interactive elements are rendered with event handlers
4. User interactions trigger the `onChatInteraction` callback
5. The callback sends appropriate messages back to continue the conversation

This creates a seamless experience where users can interact with AI-generated UI elements that feel native to the chat interface.