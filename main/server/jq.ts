export function jq(nama: string): string {
   return`
<script>
$(function(){


   $(".P2P").remove();
   $("#loadProviders a").each( function(){
     let src = decodeURIComponent( $(this).attr("href") ).split("=")[1]
     $(this).attr("href", src)
     })

  });
  </script>
`}
