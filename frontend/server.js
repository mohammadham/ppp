const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
process.loadEnvFile(path.join(__dirname, '.env'));
const { HOST, PORT, REACT_APP_BACKEND_URL } = process.env;
if (!HOST || !PORT || !REACT_APP_BACKEND_URL) throw new Error('Missing server configuration');
const backend = new URL(REACT_APP_BACKEND_URL);
if (!['http:', 'https:'].includes(backend.protocol)) throw new Error('Invalid backend URL');
const escape = value => value.replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;');
http.createServer((req, res) => {
  const pathname = new URL(req.url, backend).pathname;
  if (pathname === '/favicon.ico') { res.writeHead(204); return res.end(); }
  if (pathname !== '/' || !['GET', 'HEAD'].includes(req.method)) { res.writeHead(404); return res.end('Not found'); }
  const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8')
    .replace('__DOWNLOAD_URL__', escape(new URL('/api/thesis/download', backend).href));
  res.writeHead(200, {
    'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
    'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; base-uri 'none'; frame-ancestors 'self' https://*.emergentagent.com https://*.emergent.sh"
  });
  res.end(req.method === 'HEAD' ? undefined : html);
}).listen(Number(PORT), HOST);