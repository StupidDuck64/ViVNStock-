# SSL Certificates for Flink Nginx Proxy

This directory contains SSL certificates for the Nginx reverse proxy.

## Development - Self-Signed Certificates

For development, generate self-signed certificates:

### On Linux/Mac:
```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -subj '/CN=localhost' \
  -keyout nginx.key \
  -out nginx.crt
```

### On Windows (PowerShell):
```powershell
docker run --rm -v ${PWD}:/ssl alpine/openssl `
  req -x509 -nodes -days 365 -newkey rsa:2048 `
  -subj '/CN=localhost' `
  -keyout /ssl/nginx.key `
  -out /ssl/nginx.crt
```

### Using Docker (cross-platform):
```bash
docker run --rm -v $(pwd):/ssl alpine/openssl \
  req -x509 -nodes -days 365 -newkey rsa:2048 \
  -subj '/CN=localhost' \
  -keyout /ssl/nginx.key \
  -out /ssl/nginx.crt
```

## Production - CA-Signed Certificates

In production, use certificates from a trusted Certificate Authority:

1. Obtain certificates from your CA (e.g., Let's Encrypt, DigiCert)
2. Place the certificate files in this directory:
   - `nginx.crt` - Server certificate
   - `nginx.key` - Private key
   - `ca-bundle.crt` - (Optional) CA certificate chain

3. Update nginx configuration to use proper certificates
4. Set `ssl_verify = "yes"` in the nginx config

## File Permissions

Ensure proper permissions for security:
```bash
chmod 644 nginx.crt
chmod 600 nginx.key
```

## .gitignore

These certificate files should NOT be committed to git:
- *.key
- *.crt
- *.pem
