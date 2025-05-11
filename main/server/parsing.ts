// File: parsing.ts

import cheerio from 'https://esm.sh/cheerio@1.0.0-rc.12';
import { jq } from './jq.ts';
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

export function manipulateHtml(html: string, currentPageUrl: string, baseUrl: string, proxyPrefix: string): string {
    try {
        const $ = cheerio.load(html);

        $('a[href], link[href], script[src], img[src], form[action]').each((_i, el) => {
          const tag = $(el);
          const href = tag.attr('href');
          const src = tag.attr('src');
          const action = tag.attr('action');

          if (href) {
            tag.attr('href', rewriteUrl(currentPageUrl, baseUrl, proxyPrefix, href));
          }
          if (src) {
             tag.attr('src', rewriteUrl(currentPageUrl, baseUrl, proxyPrefix, src));
          }
          if (action) {
             tag.attr('action', rewriteUrl(currentPageUrl, baseUrl, proxyPrefix, action));
          }
        });
        $("body").append(jq("crot"));
        return $.html();

    } catch (e) {
        console.error("Error manipulating HTML with Cheerio:", e);
        return html;
    }
}
