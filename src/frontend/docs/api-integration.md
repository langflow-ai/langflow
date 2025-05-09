# API Integration Guide

This document outlines how to integrate with backend APIs in the Langflow frontend application.

## API Configuration

### Base Setup

The API configuration is managed through environment variables:

```env
VITE_API_HOST=http://localhost:7860
```

### API Client Setup

We use Axios for API requests. The base configuration is set up in `src/utils/api.ts`:

```typescript
import axios from 'axios';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_HOST,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});
```

## Authentication

### Token Management

```typescript
// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

### Authentication Flow

1. User login
2. Token storage
3. Token refresh
4. Logout

## API Endpoints

### User Management

```typescript
// Login
POST /api/auth/login
{
  "username": string,
  "password": string
}

// Register
POST /api/auth/register
{
  "username": string,
  "email": string,
  "password": string
}

// Logout
POST /api/auth/logout
```

### Flow Management

```typescript
// Get Flows
GET /api/flows

// Create Flow
POST /api/flows
{
  "name": string,
  "description": string,
  "nodes": Array<Node>
}

// Update Flow
PUT /api/flows/:id
{
  "name": string,
  "description": string,
  "nodes": Array<Node>
}

// Delete Flow
DELETE /api/flows/:id
```

## Error Handling

### Global Error Handler

```typescript
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      switch (error.response.status) {
        case 401:
          // Handle unauthorized
          break;
        case 403:
          // Handle forbidden
          break;
        case 404:
          // Handle not found
          break;
        default:
          // Handle other errors
      }
    }
    return Promise.reject(error);
  }
);
```

### Error Types

```typescript
interface ApiError {
  status: number;
  message: string;
  details?: Record<string, any>;
}
```

## Data Fetching

### React Query Setup

```typescript
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5 * 60 * 1000,
    },
  },
});
```

### Query Hooks

```typescript
// Example query hook
const useFlows = () => {
  return useQuery({
    queryKey: ['flows'],
    queryFn: () => api.get('/api/flows').then((res) => res.data),
  });
};

// Example mutation hook
const useCreateFlow = () => {
  return useMutation({
    mutationFn: (flow) => api.post('/api/flows', flow),
    onSuccess: () => {
      queryClient.invalidateQueries(['flows']);
    },
  });
};
```

## WebSocket Integration

### Socket Setup

```typescript
import { io } from 'socket.io-client';

const socket = io(import.meta.env.VITE_API_HOST, {
  autoConnect: false,
  transports: ['websocket'],
});
```

### Socket Events

```typescript
// Connect to socket
socket.connect();

// Listen for events
socket.on('flow:update', (data) => {
  // Handle flow update
});

// Emit events
socket.emit('flow:subscribe', flowId);
```

## API Response Types

### Common Response Structure

```typescript
interface ApiResponse<T> {
  data: T;
  message: string;
  status: 'success' | 'error';
}
```

### Pagination Response

```typescript
interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}
```

## Best Practices

### Request Caching

- Use React Query for automatic caching
- Implement proper cache invalidation
- Set appropriate stale times

### Error Handling

- Implement retry logic
- Show user-friendly error messages
- Log errors for debugging

### Performance

- Implement request debouncing
- Use pagination for large datasets
- Optimize payload size

### Security

- Sanitize input data
- Validate responses
- Handle sensitive data properly

## Testing

### API Mocking

```typescript
import { rest } from 'msw';

export const handlers = [
  rest.get('/api/flows', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: [],
        message: 'Success',
        status: 'success',
      })
    );
  }),
];
```

### Testing Hooks

```typescript
import { renderHook } from '@testing-library/react-hooks';

test('useFlows hook', async () => {
  const { result, waitFor } = renderHook(() => useFlows());
  
  await waitFor(() => result.current.isSuccess);
  
  expect(result.current.data).toBeDefined();
});
```

## Deployment Considerations

### Environment Configuration

- Set up environment variables
- Configure CORS settings
- Set up proper SSL certificates

### API Versioning

- Include version in URL
- Maintain backwards compatibility
- Document breaking changes

### Monitoring

- Implement request logging
- Monitor API performance
- Track error rates

## Documentation

### API Documentation

- Document all endpoints
- Include request/response examples
- Document error codes

### Type Documentation

- Document interfaces
- Include JSDoc comments
- Provide usage examples 