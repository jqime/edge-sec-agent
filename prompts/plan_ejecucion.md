# FASE 2 — PLAN DE RECONSTRUCCIÓN Y CORRECCIÓN

Usa los hallazgos ya registrados en `AGENTS.md`.

No realices cambios todavía.

Construye un plan ordenado para dejar la Orange Pi y el repositorio completamente funcionales después de una reinstalación limpia.

Divide el plan en estas categorías:

1. Correcciones del código.
2. Tests faltantes.
3. Dependencias Python.
4. Paquetes del sistema.
5. Ollama y modelo local.
6. SQLite y directorios.
7. Scripts ejecutables.
8. systemd.
9. Nginx y TLS.
10. Fail2Ban.
11. SSH y firewall.
12. Health checks.
13. Validación después de reinicio.
14. Documentación.
15. Git, commit y push.

Para cada acción especifica:

- comando exacto;
- archivo afectado;
- si es local o remoto;
- si requiere root;
- backup necesario;
- riesgo;
- validación posterior;
- rollback;
- dependencia previa.

No incluyas acciones innecesarias ni instalaciones opcionales sin justificación.

Actualiza `AGENTS.md` con el plan.

Si existe una contradicción que no pueda resolverse con evidencia, márcala como `BLOQUEADA` y no elijas arbitrariamente una solución.
