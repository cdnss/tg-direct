docker build -t tgdirect .
docker run --rm -v $(pwd):/app -p 8080:8080 tgdirect