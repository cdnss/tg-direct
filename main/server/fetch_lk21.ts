// Deno script to fetch data from lk21.film
const targetUrl = "https://lk21.film";

try {
    const response = await fetch(targetUrl);
    if (!response.ok) {
        console.error(`Failed to fetch ${targetUrl}: ${response.statusText}`);
        Deno.exit(1);
    }
    const body = await response.text();
    console.log(body);
} catch (error) {
    console.error(`Error fetching ${targetUrl}:`, error);
    Deno.exit(1);
}
