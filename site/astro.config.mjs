// @ts-check
import { defineConfig } from 'astro/config';

import cloudflare from '@astrojs/cloudflare';

// https://astro.build/config
export default defineConfig({
  site: 'https://at-piano.com',
  output: 'server',
  session: false,
  adapter: cloudflare({
    imageService: 'compile'
  })
});
