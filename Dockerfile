FROM python:3.9-slim-buster

WORKDIR /app

# Instal alat yang dibutuhkan untuk mengunduh Deno
# curl untuk mengunduh script instalasi
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# --- Instalasi Deno ---
# Unduh dan jalankan script instalasi Deno
# Secara default, Deno akan terinstal di $HOME/.deno
RUN curl -fsSL https://deno.land/install.sh | sh

# Tambahkan direktori binari Deno ke PATH
# Dalam konteks Docker (default user adalah root), $HOME adalah /root.
# Jadi Deno terinstal di /root/.deno/bin
ENV DENO_INSTALL="/root/.deno"
ENV PATH="$DENO_INSTALL/bin:$PATH"
# --- Akhir Instalasi Deno ---


COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "main"]
EXPOSE 8080
