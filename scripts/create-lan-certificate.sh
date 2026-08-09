#!/usr/bin/env bash
set -euo pipefail
umask 077

if [[ $# -lt 3 ]]; then
  echo "usage: $0 ABSOLUTE_OUTPUT_DIR DNS_NAME IP_ADDRESS" >&2
  exit 64
fi

output=$1
dns_name=$2
ip_address=$3
case "$output" in
  /*) ;;
  *) echo "output directory must be absolute" >&2; exit 64 ;;
esac
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
case "$output/" in
  "$repo_root"/*) echo "TLS material must be outside the repository" >&2; exit 64 ;;
esac
[[ "$dns_name" =~ ^[A-Za-z0-9.-]+$ ]] || { echo "invalid DNS name" >&2; exit 64; }
[[ "$ip_address" =~ ^[0-9A-Fa-f:.]+$ ]] || { echo "invalid IP address" >&2; exit 64; }

mkdir -p "$output"
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out "$output/ca.key"
openssl req -x509 -new -sha256 -days 3650 -key "$output/ca.key" \
  -subj "/CN=Personal Finance Domestic CA" -out "$output/ca.crt"
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out "$output/server.key"
openssl req -new -key "$output/server.key" -subj "/CN=$dns_name" -out "$output/server.csr"
cat >"$output/server.ext" <<EOF
subjectAltName=DNS:$dns_name,IP:$ip_address,IP:127.0.0.1,DNS:localhost
extendedKeyUsage=serverAuth
keyUsage=digitalSignature,keyEncipherment
EOF
openssl x509 -req -sha256 -days 397 -in "$output/server.csr" \
  -CA "$output/ca.crt" -CAkey "$output/ca.key" -CAcreateserial \
  -extfile "$output/server.ext" -out "$output/server.crt"
chmod 600 "$output/ca.key" "$output/server.key"
chmod 644 "$output/ca.crt" "$output/server.crt"
rm -f "$output/server.csr" "$output/server.ext" "$output/ca.srl"
echo "CA certificate: $output/ca.crt"
echo "Server certificate: $output/server.crt"
