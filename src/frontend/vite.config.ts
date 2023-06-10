import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
import svgr from 'vite-plugin-svgr';
const apiRoutes = [
	'/all',
	'/predict',
	'^/validate/*',
	'^/chat/*',
	'/version',
	'/health',
];

// Use environment variable to determine the target.
const target = process.env.VITE_PROXY_TARGET || 'http://192.168.47.15:8000';

const proxyTargets = apiRoutes.reduce((proxyObj, route) => {
	proxyObj[route] = {
		target: target,
		changeOrigin: true,
		secure: false,
		ws: true,
		rewrite: (path) => `/api/v1${path}`,
	};
	return proxyObj;
}, {});

export default defineConfig(() => {
	return {
		build: {
			outDir: 'build',
		},
		plugins: [react(), svgr()],
		server: {
			port: 3001,
			proxy: {
				...proxyTargets,
			},
		},
	};
});
