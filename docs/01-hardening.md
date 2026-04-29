# Hardening del Sistema

## Comandos ejecutados
\`\`\`bash
apt update && apt upgrade -y
apt install ufw fail2ban auditd unattended-upgrades -y
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw enable
systemctl enable fail2ban --now
systemctl enable auditd --now
\`\`\`

## Verificación
\`\`\`bash
ufw status verbose
systemctl status fail2ban
systemctl status auditd
\`\`\`
