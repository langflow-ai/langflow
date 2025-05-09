# Component Documentation

This document provides detailed information about the reusable components in the Langflow frontend.

## Component Categories

### Layout Components

#### MainLayout
The main layout wrapper for the application.

```typescript
import { MainLayout } from '@/components/layout/MainLayout';

<MainLayout>
  <YourContent />
</MainLayout>
```

**Props:**
- `children`: React.ReactNode
- `className?`: string

### UI Components

#### Button
Standard button component with variants.

```typescript
import { Button } from '@/components/ui/Button';

<Button
  variant="primary"
  size="md"
  onClick={() => {}}
>
  Click Me
</Button>
```

**Props:**
- `variant`: 'primary' | 'secondary' | 'outline' | 'ghost'
- `size`: 'sm' | 'md' | 'lg'
- `onClick`: () => void
- `disabled?`: boolean
- `className?`: string

#### Input
Text input component with validation support.

```typescript
import { Input } from '@/components/ui/Input';

<Input
  type="text"
  placeholder="Enter text"
  value={value}
  onChange={(e) => setValue(e.target.value)}
/>
```

**Props:**
- `type`: 'text' | 'password' | 'email' | 'number'
- `value`: string
- `onChange`: (e: ChangeEvent<HTMLInputElement>) => void
- `placeholder?`: string
- `error?`: string
- `className?`: string

### Form Components

#### Form
Form wrapper component with validation.

```typescript
import { Form } from '@/components/form/Form';

<Form onSubmit={handleSubmit}>
  <Form.Field>
    <Form.Label>Username</Form.Label>
    <Form.Input name="username" />
    <Form.Error name="username" />
  </Form.Field>
</Form>
```

**Props:**
- `onSubmit`: (data: FormData) => void
- `children`: React.ReactNode
- `className?`: string

### Data Display

#### Table
Reusable table component with sorting and pagination.

```typescript
import { Table } from '@/components/data/Table';

<Table
  data={data}
  columns={columns}
  pagination={true}
  sortable={true}
/>
```

**Props:**
- `data`: Array<any>
- `columns`: TableColumn[]
- `pagination?`: boolean
- `sortable?`: boolean
- `className?`: string

### Navigation

#### Tabs
Tab navigation component.

```typescript
import { Tabs } from '@/components/navigation/Tabs';

<Tabs>
  <Tabs.List>
    <Tabs.Tab>Tab 1</Tabs.Tab>
    <Tabs.Tab>Tab 2</Tabs.Tab>
  </Tabs.List>
  <Tabs.Panels>
    <Tabs.Panel>Content 1</Tabs.Panel>
    <Tabs.Panel>Content 2</Tabs.Panel>
  </Tabs.Panels>
</Tabs>
```

**Props:**
- `defaultIndex?`: number
- `onChange?`: (index: number) => void
- `children`: React.ReactNode

### Feedback

#### Alert
Alert component for notifications and messages.

```typescript
import { Alert } from '@/components/feedback/Alert';

<Alert
  type="success"
  title="Success!"
  message="Operation completed successfully"
/>
```

**Props:**
- `type`: 'success' | 'error' | 'warning' | 'info'
- `title`: string
- `message`: string
- `onClose?`: () => void

### Modal

#### Dialog
Modal dialog component.

```typescript
import { Dialog } from '@/components/modal/Dialog';

<Dialog
  open={isOpen}
  onClose={() => setIsOpen(false)}
  title="Dialog Title"
>
  <Dialog.Content>
    Your content here
  </Dialog.Content>
</Dialog>
```

**Props:**
- `open`: boolean
- `onClose`: () => void
- `title`: string
- `children`: React.ReactNode
- `size?`: 'sm' | 'md' | 'lg'

### Icons

#### Icon
SVG icon component.

```typescript
import { Icon } from '@/components/icons/Icon';

<Icon
  name="check"
  size="md"
  color="green"
/>
```

**Props:**
- `name`: IconName
- `size?`: 'sm' | 'md' | 'lg'
- `color?`: string
- `className?`: string

## Component Best Practices

### Performance
- Use React.memo for pure components
- Implement proper prop types
- Avoid unnecessary re-renders

### Accessibility
- Include ARIA labels
- Support keyboard navigation
- Maintain proper focus management

### Styling
- Use Tailwind CSS utilities
- Follow design system
- Support dark mode

### Error Handling
- Implement error boundaries
- Provide fallback UI
- Log errors appropriately

## Component Development Guidelines

### Creating New Components
1. Create component file
2. Define TypeScript interfaces
3. Implement component
4. Add documentation
5. Create tests

### Testing Components
1. Write unit tests
2. Test accessibility
3. Test edge cases
4. Test responsiveness

### Documentation
1. Include JSDoc comments
2. Provide usage examples
3. Document props
4. Add change history

## Component Architecture

### File Structure
```
components/
├── ui/
│   ├── Button/
│   │   ├── Button.tsx
│   │   ├── Button.test.tsx
│   │   └── index.ts
│   └── Input/
│       ├── Input.tsx
│       ├── Input.test.tsx
│       └── index.ts
└── layout/
    └── MainLayout/
        ├── MainLayout.tsx
        ├── MainLayout.test.tsx
        └── index.ts
```

### Code Organization
- Group related components
- Maintain consistent structure
- Use index files for exports

## Component Lifecycle

### Mounting
- Initialize state
- Set up subscriptions
- Load initial data

### Updating
- Handle prop changes
- Update internal state
- Trigger side effects

### Unmounting
- Clean up subscriptions
- Cancel pending requests
- Clear timeouts/intervals 