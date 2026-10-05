# FASE 1 — AUDITORÍA SIN MODIFICACIONES

Trabaja sobre `jqime/edge-sec-agent`.

En esta fase no modifiques:
- firewall;
- SSH;
- Nginx;
- Fail2Ban;
- systemd;
- base de datos de producción;
- secretos;
- configuración del sistema.

Lee primero `OPENCODE_EDGE_SEC_AGENT_MASTER_PROMPT.md` y todos los archivos obligatorios indicados allí.

Después:

1. Comprueba el estado de Git.
2. Comprueba si existe `AGENTS.md`.
3. Crea o actualiza `AGENTS.md`.
4. Lee el repositorio completo y sus documentos.
5. Ejecuta una auditoría local:
   - Python;
   - Shell;
   - PowerShell;
   - tests;
   - Docker;
   - systemd;
   - Nginx;
   - documentación;
   - configuración de secretos.
6. Comprueba si existe acceso SSH a la Orange Pi.
7. Si existe acceso, realiza únicamente diagnóstico remoto de solo lectura.
8. Detecta todas las contradicciones entre documentación y código.
9. Detecta todos los problemas que impiden una instalación limpia.
10. No corrijas todavía ningún problema.

Registra todo en `AGENTS.md`.

Genera al final una tabla:

| ID | Problema | Severidad | Evidencia | Archivo/servicio | Riesgo | Solución propuesta |
|---|---|---:|---|---|---|---|

Termina únicamente con:
- estado de Git;
- estado de la Orange Pi;
- problemas encontrados;
- problemas bloqueantes;
- plan recomendado;
- elementos `NO VERIFICADOS`.

No hagas commit ni push en esta fase.
