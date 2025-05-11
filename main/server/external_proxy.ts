// File: external_proxy.ts

async function processExternalRequest() {
  try {
    const inputJsonString = await Deno.stdin.text();
    const requestData = JSON.parse(inputJsonString);

    const { targetUrl, method, headers, body } = requestData;

    const decodedTargetUrl = decodeURIComponent(targetUrl);

    const response = await fetch(decodedTargetUrl, {
      method: method,
      headers: headers,
      body: typeof body === 'string' ? body : undefined,
    });

    const outputHeaders: Record<string, string> = {};
    response.headers.forEach((value, name) => {
      const lowerName = name.toLowerCase();
      if (!['content-encoding', 'connection', 'transfer-encoding', 'content-length', 'set-cookie',
           'content-security-policy', 'x-frame-options'].includes(lowerName)) {
        outputHeaders[name] = value;
      } else {
          console.log(`[ExternalProxy] Removing header: ${name}`);
      }
    });

    const buffer = await response.arrayBuffer();
    const outputBody = btoa(String.fromCharCode(...new Uint8Array(buffer)));
    outputHeaders['X-Proxy-Body-Encoding'] = 'base64';

    const output = {
      status: response.status,
      headers: outputHeaders,
      body: outputBody,
    };

    console.log(JSON.stringify(output));

  } catch (e) {
    console.error("Error in external_proxy.ts script:", e);
    console.log(JSON.stringify({
      status: 500,
      headers: { 'Content-Type': 'text/plain' },
      body: `Deno External Proxy Error: ${e.message || String(e)}`,
    }));
     Deno.exit(1);
  }
}

processExternalRequest();
