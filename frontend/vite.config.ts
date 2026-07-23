import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		proxy: {
			'/backend': {
				target: 'https://saheldust-backend.onrender.com',
				changeOrigin: true,
				secure: true,
				rewrite: (path) => path.replace(/^\/backend/, '')
			}
		}
	}
});
