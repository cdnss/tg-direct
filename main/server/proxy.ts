// File: proxy.ts

import { manipulateHtml } from './parsing.ts';

async function processRequest() {
  try {
    const inputJsonString = await Deno.stdin.text();
    const requestData = JSON.parse(inputJsonString);

    const { targetUrl, baseUrl, method, headers, body, proxyPrefix } = requestData;

    const decodedTargetUrl = decodeURIComponent(targetUrl);

    const response = await fetch(decodedTargetUrl, {
      method: method,
      headers: headers,
      body: typeof body === 'string' ? body : undefined,
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
        outputBody = manipulateHtml(html, decodedTargetUrl, baseUrl, proxyPrefix);

      } catch (e) {
        console.error("Error processing HTML:", e);
        outputBody = html;
      }
    } else {
      const buffer = await response.arrayBuffer();
      outputBody = btoa(String.fromCharCode(...new Uint8Array(buffer)));
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
