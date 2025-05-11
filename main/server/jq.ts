export function jq(nama: string): string {`
$(function(){
   $("#loadProviders a").each( function(){
     let src = decodeURIComponent( $(this).attr("href") ).split("=")
     $(this).attr("href", src)
     })

  });
`}
