// usage: node render.mjs <startFrame> <endFrame> [outDir] [timesCSV]
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const root = path.dirname(new URL(import.meta.url).pathname);
const FPS = 30;
const [s = '0', e = '900', out = path.join(root, 'frames'), times] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript' };
const server = http.createServer((req, res) => {
  const p = path.join(root, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(root) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'content-type': types[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
}).listen(0);
const port = server.address().port;

const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
page.on('console', m => console.log('[page]', m.text()));
page.on('pageerror', e => console.log('[pageerror]', e.message));
await page.goto(`http://127.0.0.1:${port}/scene.html`);
await page.waitForFunction('window.ready === true', null, { timeout: 300000 });

const list = times ? times.split(',').map(Number).map(t => [Math.round(t * FPS), t]) : [];
if (!times) for (let f = +s; f < +e; f++) list.push([f, f / FPS]);
const t0 = Date.now();
for (const [f, t] of list) {
  await page.evaluate(([t, f]) => window.renderAt(t, f), [t, f]);
  await page.screenshot({ path: path.join(out, `f_${String(f).padStart(4, '0')}.jpg`), type: 'jpeg', quality: 94 });
  if (f % 30 === 0) console.log(`frame ${f} ${((Date.now() - t0) / 1000).toFixed(1)}s`);
}
console.log('done', list.length, 'frames in', ((Date.now() - t0) / 1000).toFixed(1), 's');
await browser.close(); server.close();
