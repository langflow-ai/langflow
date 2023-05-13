import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';

const apiRoutes = [
    '/all',
    '/predict',
    '^/validate/*',
    '^/chat/*',
];

const proxyTargets = apiRoutes.reduce((proxyObj, route) => {
    proxyObj[route] = {
        target: 'http://127.0.0.1:7860',
        changeOrigin: true,
        secure: false,
        ws: true,
    };
    return proxyObj;
}, {});

export default defineConfig(() => {
    return {
        build: {
            outDir: 'build',
        },
        plugins: [react()],
        server: {
            port: 3000,
            proxy: {
                ...proxyTargets
            }
        },
    };
});