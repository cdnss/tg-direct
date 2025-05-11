export function jq(nama: string): string {`
<script>
$(function(){
   $("#loadProviders a").each( function(){
     let src = decodeURIComponent( $(this).attr("href") ).split("=")
     $(this).attr("href", src)
     })

  });
  </script>
`}
