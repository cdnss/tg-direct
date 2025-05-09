// File: proxy.ts
import * as cheerio from 'https://esm.sh/cheerio@1.0.0-rc.12';
import { URL } from 'node:url';

function rewriteUrl(currentPageUrl: string, baseUrl: string, proxyPrefix: string, urlToRewrite: string): string {
  if (!urlToRewrite || urlToRewrite.match(/^(mailto|tel|javascript|#|data):/)) {
    return urlToRewrite;
  }

  try {
    const absoluteUrl = new URL(urlToRewrite, currentPageUrl);
    const baseUrlObject = new URL(baseUrl);

    if (absoluteUrl.hostname !== baseUrlObject.hostname) {
         return absoluteUrl.toString();
    }

    const finalPath = absoluteUrl.pathname + absoluteUrl.search;
    return proxyPrefix.replace(/\/+$/, '') + '/' + finalPath.replace(/^\/+/, '');

  } catch (e) {
    console.error("Error rewriting URL:", urlToRewrite, e);
    return urlToRewrite;
  }
}

async function processRequest() {
  try {
    const inputJsonString = await Deno.readAll(Deno.stdin);
    const requestData = JSON.parse(new TextDecoder().decode(inputJsonString));

    const { targetUrl, baseUrl, method, headers, body, proxyPrefix } = requestData;

    const response = await fetch(targetUrl, {
      method: method,
      headers: headers,
      body: typeof body === 'string' ? body : undefined, // Ensure body is string or undefined
    });

    const outputHeaders: Record<string, string> = {};
    response.headers.forEach((value, name) => {
      if (!['content-encoding', 'connection', 'transfer-encoding', 'content-length', 'set-cookie'].includes(name.toLowerCase())) {
         outputHeaders[name] = value;
      }
    });

    let outputBody: string;
    const contentType = response.headers.get('content-type') || '';

    if (contentType.includes('text/html') && response.status < 400) {
      const html = await response.text();
      try {
        const $ = cheerio.load(html);

        $('a[href], link[href], script[src], img[src], form[action]').each((_i, el) => {
          const tag = $(el);
          const href = tag.attr('href');
          const src = tag.attr('src');
          const action = tag.attr('action');

          if (href) {
            tag.attr('href', rewriteUrl(targetUrl, baseUrl, proxyPrefix, href));
          }
          if (src) {
             tag.attr('src', rewriteUrl(targetUrl, baseUrl, proxyPrefix, src));
          }
          if (action) {
             tag.attr('action', rewriteUrl(targetUrl, baseUrl, proxyPrefix, action));
          }
        });

        outputBody = $.html();

      } catch (e) {
        console.error("Error processing HTML with Cheerio:", e);
        outputBody = html;
      }
    } else {
      // Handle other content types (e.g., images, CSS, JS) as base64
      const buffer = await response.arrayBuffer();
      outputBody = Deno.btoa(String.fromCharCode(...new Uint8Array(buffer)));
      outputHeaders['X-Proxy-Body-Encoding'] = 'base64';
    }

    const output = {
      status: response.status,
      headers: outputHeaders,
      body: outputBody,
    };

    console.log(JSON.stringify(output));

  } catch (e) {
    console.error("Error in Deno script:", e);
    console.log(JSON.stringify({
      status: 500,
      headers: { 'Content-Type': 'text/plain' },
      body: `Deno Proxy Error: ${e.message || String(e)}`,
    }));
     Deno.exit(1);
  }
}

processRequest();
