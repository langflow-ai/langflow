# Getting Started with Langflow Frontend

This guide will help you set up and run the Langflow frontend application locally.

## Prerequisites

- Node.js (v16 or higher)
- npm (v7 or higher)
- Git

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd langflow-frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

## Development Environment

1. Start the development server:
   ```bash
   npm start
   ```
   This will start the Vite development server at http://localhost:3000

2. For Docker-based development:
   ```bash
   npm run dev:docker
   ```

## Environment Configuration

Create a `.env` file in the root directory with the following variables:
```env
VITE_API_HOST=http://localhost:7860
```

## Code Quality Tools

- **TypeScript Type Checking**:
  ```bash
  npm run type-check
  ```

- **Code Formatting**:
  ```bash
  npm run format
  ```

- **Format Checking**:
  ```bash
  npm run check-format
  ```

## Building for Production

1. Create a production build:
   ```bash
   npm run build
   ```

2. Preview the production build locally:
   ```bash
   npm run serve
   ```

## Troubleshooting

### Common Issues

1. **Port Already in Use**
   - Error: `Port 3000 is already in use`
   - Solution: Kill the process using the port or use a different port:
     ```bash
     export PORT=3001 && npm start
     ```

2. **Node Version Mismatch**
   - Use `nvm` (Node Version Manager) to switch to the correct Node version:
     ```bash
     nvm use 16
     ```

3. **Dependencies Issues**
   - Try removing node_modules and reinstalling:
     ```bash
     rm -rf node_modules
     npm install
     ```

## Next Steps

- Read the [Architecture Overview](architecture.md) to understand the project structure
- Check out the [Development Guide](development.md) for coding standards and best practices
- Review the [Component Documentation](components.md) to learn about available components 