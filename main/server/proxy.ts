
import { manipulateHtml } from './parsing.ts';

async function readAllManual(reader: Deno.Reader): Promise<Uint8Array> {
  const chunks: Uint8Array[] = [];
  const buf = new Uint8Array(4096);
  while (true) {
    const nread = await reader.read(buf);
    if (nread === null) {
      break;
    }
    chunks.push(buf.slice(0, nread));
  }
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const result = new Uint8Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.length;
  }
  return result;
}

async function processRequest() {
  try {
    const inputBytes = await readAllManual(Deno.stdin);
    const inputJsonString = new TextDecoder().decode(inputBytes);
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
      const lowerName = name.toLowerCase();
      if (!['content-encoding', 'connection', 'transfer-encoding', 'content-length', 'set-cookie'].includes(lowerName)) {
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
