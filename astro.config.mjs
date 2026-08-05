// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';

// https://astro.build/config
export default defineConfig({
  // Replace with your actual GitHub Pages URL:
  //   Project page → site: "https://<username>.github.io", base: "/<repo>/"
  //   User page    → site: "https://<username>.github.io", base: "/"
  //   Custom domain → site: "https://example.com",         base: "/"
  site: "https://llmons.github.io",
  base: "/lang-trends/",
  vite: {
    plugins: [tailwindcss()],
  },
});
