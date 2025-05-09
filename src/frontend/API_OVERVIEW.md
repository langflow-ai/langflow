# Langflow Frontend API & Codebase Overview

---

## 1. Project Structure Overview

- **Main directories:**
  - `src/`: Main application code.
    - `controllers/API/`: All API logic, helpers, and endpoint definitions.
    - `constants/`: Global constants, including API base URLs.
    - `customization/`: Project-specific overrides, including API base URLs.
    - `pages/`, `components/`, `modals/`, etc.: UI and feature logic.
    - `utils/`, `helpers/`: Utility and helper functions.
  - `public/`, `assets/`, `styles/`: Static assets and styling.
  - `tests/`: Test files.

---

## 2. API Base URLs and Configuration

- **Base URLs:**
  - Defined in `src/constants/constants.ts` and `src/customization/config-constants.ts`:
    - `BASE_URL_API = "/api/v1/"`
    - `BASE_URL_API_V2 = "/api/v2/"`
  - These can be overridden by values in `customization/config-constants.ts` if needed.

- **Proxy Target:**
  - `PROXY_TARGET = "http://127.0.0.1:7860"` (used for some direct server calls, e.g., SSE).

---

## 3. API Call Implementations

### Axios Instance

- **File:** `src/controllers/API/api.tsx`
- **Setup:**
  - An Axios instance (`api`) is created for all API calls.
  - Interceptors are set up to:
    - Attach authentication tokens.
    - Add custom headers.
    - Handle error retries and token refresh.
    - Prevent duplicate requests (via `checkDuplicateRequestAndStoreRequest`).

### Fetch Usage

- Used for:
  - File downloads (to avoid Axios blob issues).
  - Streaming requests (e.g., SSE or long-polling).

### API Endpoint Construction

- **Helper:** `src/controllers/API/helpers/constants.ts`
  - `getURL(key, params, v2)` builds endpoint URLs using the base URL and a key from a central `URLs` object.
  - Example: `getURL("FILES")` → `/api/v1/files`

### API Service Layer

- **File:** `src/controllers/API/index.ts`
  - Exports functions for each API endpoint, e.g.:
    - `createApiKey`, `saveFlowStore`, `getStoreComponents`, `getComponent`, etc.
  - All use the `api` Axios instance and `BASE_URL_API` for endpoint construction.

### React Query Integration

- **File:** `src/controllers/API/services/request-processor.ts`
  - Provides `UseRequestProcessor` for mutation/query hooks using React Query.
  - Used for data fetching and mutation with caching and retries.

---

## 4. API Call Examples

- **Standard API Call (Axios):**
  ```ts
  const res = await api.post(`${BASE_URL_API}api_key/`, { name });
  ```
- **File Download (Fetch):**
  ```ts
  const response = await fetch(`${getURL("FILES")}/download/${params.path}`, { ... });
  ```
- **Streaming Request:**
  ```ts
  const response = await fetch(url, params);
  // Stream handling logic...
  ```

---

## 5. Authentication and Headers

- **Token Handling:**
  - Access tokens are stored in cookies.
  - Axios and fetch interceptors attach tokens to requests.
  - Automatic token refresh and logout on repeated authentication errors.

- **Custom Headers:**
  - Added to requests to the same origin (not external APIs).

---

## 6. API Endpoint Keys

- Centralized in `src/controllers/API/helpers/constants.ts`:
  - Examples: `FILES`, `STORE`, `API_KEY`, `FLOWS`, `BUILD`, `MCP`, etc.
  - Used with `getURL` to generate full endpoint paths.

---

## 7. Duplicate Request Prevention

- **File:** `src/controllers/API/helpers/check-duplicate-requests.ts`
  - Prevents rapid, repeated GET requests to the same endpoint.

---

## 8. Routing and API Context

- **File:** `src/routes.tsx`
  - No direct API logic, but sets up the app's page structure and context providers.

---

## 9. Customization and Environment

- **File:** `src/customization/config-constants.ts`
  - Allows overriding of base URLs, proxy targets, and other environment-specific settings.

---

## 10. Summary Table

| Aspect                | File(s) / Location                                      | Details                                                                 |
|-----------------------|--------------------------------------------------------|-------------------------------------------------------------------------|
| Base URL              | `constants/constants.ts`, `customization/config-constants.ts` | `/api/v1/`, `/api/v2/` (overridable)                                   |
| API Instance          | `controllers/API/api.tsx`                              | Axios instance with interceptors                                        |
| API Endpoints         | `controllers/API/helpers/constants.ts`                 | Centralized keys, used with `getURL`                                    |
| API Calls             | `controllers/API/index.ts`, queries, services          | Functions for each endpoint, use Axios or fetch as needed               |
| File Downloads        | `controllers/API/queries/files/use-download-files.ts`  | Uses fetch for blob handling                                            |
| Streaming             | `controllers/API/api.tsx`                              | Custom fetch-based streaming logic                                      |
| Auth/Headers          | `controllers/API/api.tsx`                              | Token from cookies, custom headers, auto-refresh                        |
| Duplicate Prevention  | `controllers/API/helpers/check-duplicate-requests.ts`  | Prevents rapid duplicate GETs                                           |
| React Query           | `controllers/API/services/request-processor.ts`        | Query/mutation hooks for data fetching/mutation                         |
| Customization         | `customization/config-constants.ts`                    | Proxy, base URLs, etc.                                                  |

---

## 11. Additional Notes

- **All API endpoints are versioned and routed through `/api/v1/` or `/api/v2/` by default.**
- **Authentication is handled via cookies and automatic token refresh.**
- **API endpoint construction is centralized for maintainability and consistency.**
- **React Query is used for robust data fetching and mutation with caching and retries.**

---

*For further details or a list of all endpoint keys and their usage, see `src/controllers/API/helpers/constants.ts` and the exported functions in `src/controllers/API/index.ts`.* 