# FASE 3 — EJECUCIÓN CONTROLADA POR BLOQUES

Ejecuta el plan aprobado de `AGENTS.md` por bloques pequeños.

Orden obligatorio:

1. Tests y correcciones locales.
2. Entorno Python.
3. SQLite y directorios.
4. Ollama.
5. Scripts.
6. systemd.
7. Nginx.
8. Fail2Ban.
9. SSH y firewall.
10. Reinicio.
11. Validación final.

Para cada bloque:

1. Explica qué vas a cambiar.
2. Guarda backups si aplica.
3. Aplica únicamente el cambio mínimo.
4. Revisa el diff.
5. Valida sintaxis.
6. Reinicia solo el servicio necesario.
7. Ejecuta pruebas específicas.
8. Registra el resultado en `AGENTS.md`.
9. Continúa solo si el bloque está validado.

Si un bloque falla:
- detente;
- ejecuta rollback si es seguro;
- registra la causa;
- no continúes con los bloques dependientes.

Nunca mezcles en el mismo paso cambios de firewall, Nginx, systemd y aplicación.
