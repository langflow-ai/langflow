# Contributing Guidelines

Thank you for considering contributing to the Langflow frontend project! This document provides guidelines and instructions for contributing.

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md) to maintain a respectful and inclusive environment.

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/langflow-frontend.git
   cd langflow-frontend
   ```
3. Install dependencies:
   ```bash
   npm install
   ```
4. Create a new branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Process

### 1. Setting Up Development Environment

- Use Node.js version 16 or higher
- Install recommended VS Code extensions
- Set up ESLint and Prettier
- Configure environment variables

### 2. Making Changes

#### Code Style

- Follow TypeScript best practices
- Use functional components
- Implement proper type definitions
- Follow project structure conventions

#### Commit Guidelines

Follow conventional commits:

```
feat: add new feature
fix: resolve bug
docs: update documentation
style: format code
refactor: restructure code
test: add tests
chore: update dependencies
```

### 3. Testing

#### Running Tests

```bash
# Unit tests
npm run test

# E2E tests
npm run test:e2e

# Test coverage
npm run test:coverage
```

#### Writing Tests

- Write unit tests for new components
- Add integration tests for features
- Maintain test coverage
- Test edge cases

### 4. Documentation

#### Code Documentation

- Add JSDoc comments
- Document complex logic
- Update component documentation
- Include usage examples

#### Update Documentation Files

- Update README if needed
- Add feature documentation
- Document breaking changes
- Update API documentation

### 5. Pull Request Process

1. Update your fork:
   ```bash
   git remote add upstream https://github.com/original/langflow-frontend.git
   git fetch upstream
   git rebase upstream/main
   ```

2. Push changes:
   ```bash
   git push origin feature/your-feature-name
   ```

3. Create Pull Request:
   - Use clear title and description
   - Reference related issues
   - Add screenshots if applicable
   - Complete PR checklist

#### PR Checklist

- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Code follows style guidelines
- [ ] All tests passing
- [ ] No linting errors
- [ ] Reviewed by self

## Code Review Process

### Reviewer Guidelines

1. Code Quality
   - Check code style
   - Verify test coverage
   - Review documentation
   - Check performance impact

2. Functionality
   - Test feature locally
   - Verify edge cases
   - Check error handling
   - Review security implications

3. Documentation
   - Verify documentation accuracy
   - Check for clear examples
   - Review API documentation
   - Validate changelog updates

### Review Response

- Address all comments
- Explain complex changes
- Update based on feedback
- Request re-review when ready

## Development Guidelines

### Component Development

1. Create new component:
   ```typescript
   // src/components/YourComponent/YourComponent.tsx
   interface YourComponentProps {
     // Props definition
   }

   export const YourComponent: React.FC<YourComponentProps> = (props) => {
     // Component implementation
   };
   ```

2. Add tests:
   ```typescript
   // src/components/YourComponent/YourComponent.test.tsx
   import { render, screen } from '@testing-library/react';
   import { YourComponent } from './YourComponent';

   describe('YourComponent', () => {
     it('renders correctly', () => {
       // Test implementation
     });
   });
   ```

3. Add documentation:
   ```typescript
   /**
    * YourComponent description
    * @param props - Component props
    * @returns JSX.Element
    */
   ```

### State Management

1. Create store:
   ```typescript
   interface YourStore {
     // Store state
   }

   export const useYourStore = create<YourStore>((set) => ({
     // Store implementation
   }));
   ```

2. Use hooks:
   ```typescript
   const useYourHook = () => {
     // Hook implementation
   };
   ```

### Styling Guidelines

1. Use Tailwind CSS:
   ```typescript
   const Component = () => (
     <div className="flex items-center justify-between p-4">
       {/* Component content */}
     </div>
   );
   ```

2. Create custom styles:
   ```typescript
   const styles = {
     wrapper: "flex items-center justify-between p-4",
     title: "text-xl font-bold text-gray-900",
   };
   ```

## Release Process

### Version Management

1. Update version:
   ```bash
   npm version patch|minor|major
   ```

2. Update changelog:
   ```markdown
   ## [1.0.0] - YYYY-MM-DD
   ### Added
   - New feature
   ### Changed
   - Updated feature
   ### Fixed
   - Bug fix
   ```

### Release Checklist

- [ ] Version updated
- [ ] Changelog updated
- [ ] Tests passing
- [ ] Documentation updated
- [ ] PR reviewed
- [ ] Release notes prepared

## Getting Help

### Resources

- Project documentation
- Component library
- API documentation
- Style guide

### Communication Channels

- GitHub Issues
- Discussion forum
- Team chat
- Email support

## License

By contributing, you agree that your contributions will be licensed under the project's license. 