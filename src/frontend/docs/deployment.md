# Deployment Guide

This guide covers the deployment process for the Langflow frontend application.

## Build Process

### Production Build

1. Create production build:
   ```bash
   npm run build
   ```

2. The build output will be in the `build/` directory:
   ```
   build/
   ├── assets/
   ├── index.html
   └── ...
   ```

### Environment Configuration

Create a `.env.production` file:
```env
VITE_API_HOST=https://api.your-domain.com
NODE_ENV=production
```

## Deployment Options

### Docker Deployment

1. Build the Docker image:
   ```bash
   docker build -t langflow-frontend:latest .
   ```

2. Run the container:
   ```bash
   docker run -p 80:80 langflow-frontend:latest
   ```

#### Docker Compose

```yaml
version: '3.8'
services:
  frontend:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "80:80"
    environment:
      - VITE_API_HOST=https://api.your-domain.com
```

### Static Hosting

#### Nginx Configuration

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass https://api.your-domain.com;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### Apache Configuration

```apache
<VirtualHost *:80>
    ServerName your-domain.com
    DocumentRoot /var/www/html

    <Directory /var/www/html>
        RewriteEngine On
        RewriteBase /
        RewriteRule ^index\.html$ - [L]
        RewriteCond %{REQUEST_FILENAME} !-f
        RewriteCond %{REQUEST_FILENAME} !-d
        RewriteRule . /index.html [L]
    </Directory>

    ProxyPass /api https://api.your-domain.com
    ProxyPassReverse /api https://api.your-domain.com
</VirtualHost>
```

### Cloud Platforms

#### AWS S3 + CloudFront

1. Create S3 bucket
2. Upload build files
3. Configure CloudFront distribution
4. Set up custom domain

#### Netlify

1. Connect repository
2. Configure build settings:
   ```toml
   [build]
     command = "npm run build"
     publish = "build"
   
   [[redirects]]
     from = "/*"
     to = "/index.html"
     status = 200
   ```

#### Vercel

1. Import repository
2. Configure project:
   ```json
   {
     "version": 2,
     "builds": [
       {
         "src": "package.json",
         "use": "@vercel/static-build"
       }
     ],
     "routes": [
       {
         "src": "/(.*)",
         "dest": "/index.html"
       }
     ]
   }
   ```

## SSL Configuration

### Let's Encrypt

1. Install Certbot:
   ```bash
   apt-get install certbot
   ```

2. Generate certificate:
   ```bash
   certbot certonly --webroot -w /var/www/html -d your-domain.com
   ```

3. Configure Nginx:
   ```nginx
   server {
       listen 443 ssl;
       server_name your-domain.com;
       
       ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
       
       # ... rest of configuration
   }
   ```

## Monitoring and Logging

### Application Monitoring

1. Set up error tracking (e.g., Sentry):
   ```typescript
   import * as Sentry from "@sentry/react";

   Sentry.init({
     dsn: "your-sentry-dsn",
     environment: process.env.NODE_ENV,
   });
   ```

2. Configure analytics (e.g., Google Analytics):
   ```html
   <!-- Google Analytics -->
   <script async src="https://www.googletagmanager.com/gtag/js?id=GA_ID"></script>
   ```

### Performance Monitoring

1. Set up web vitals reporting:
   ```typescript
   import { reportWebVitals } from './reportWebVitals';
   
   reportWebVitals(console.log);
   ```

2. Configure error boundary:
   ```typescript
   import { ErrorBoundary } from 'react-error-boundary';
   
   <ErrorBoundary FallbackComponent={ErrorFallback}>
     <App />
   </ErrorBoundary>
   ```

## Security Considerations

### Headers Configuration

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

### Content Security Policy

```html
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline';">
```

## Continuous Deployment

### GitHub Actions

```yaml
name: Deploy

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Node.js
        uses: actions/setup-node@v2
        with:
          node-version: '16'
          
      - name: Install dependencies
        run: npm ci
        
      - name: Build
        run: npm run build
        
      - name: Deploy
        # Add deployment steps
```

### GitLab CI

```yaml
stages:
  - build
  - deploy

build:
  stage: build
  script:
    - npm ci
    - npm run build
  artifacts:
    paths:
      - build/

deploy:
  stage: deploy
  script:
    # Add deployment steps
```

## Rollback Procedures

### Version Control

1. Tag releases:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. Rollback to previous version:
   ```bash
   git checkout v0.9.0
   npm ci
   npm run build
   # Deploy build
   ```

### Docker Rollback

1. Pull previous version:
   ```bash
   docker pull langflow-frontend:previous
   ```

2. Stop current container:
   ```bash
   docker stop langflow-frontend
   ```

3. Start previous version:
   ```bash
   docker run -d langflow-frontend:previous
   ```

## Troubleshooting

### Common Issues

1. **White Screen After Deployment**
   - Check if all assets are loaded
   - Verify base URL configuration
   - Check console for errors

2. **API Connection Issues**
   - Verify API endpoint configuration
   - Check CORS settings
   - Validate SSL certificates

3. **Performance Issues**
   - Analyze bundle size
   - Check for memory leaks
   - Monitor server resources

### Debug Tools

1. Source Maps:
   ```javascript
   {
     "scripts": {
       "build": "GENERATE_SOURCEMAP=true npm run build"
     }
   }
   ```

2. Performance Monitoring:
   ```typescript
   if (process.env.NODE_ENV === 'production') {
     console.log = () => {};
     console.debug = () => {};
   }
   ``` 