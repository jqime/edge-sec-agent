# Despliegue de OpenClaw

\`\`\`bash
docker run --name openclaw -it -d \
  -p 18789:18789 \
  -v /tmp:/tmp \
  -v /usr/share/zoneinfo/Europe/Madrid:/etc/localtime \
  --restart unless-stopped \
  swr.cn-north-4.myhuaweicloud.com/toolsmanhehe/openclaw:2026.2.6-3-py310-ubuntu22.04-aarch64
\`\`\`

## Verificación
\`\`\`bash
docker ps
docker logs openclaw
\`\`\`
