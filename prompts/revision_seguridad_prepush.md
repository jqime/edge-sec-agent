# REVISIÓN DE SEGURIDAD PRE-PUSH

Antes de subir cambios al repositorio, realiza una revisión específica de seguridad.

Comprueba sin imprimir secretos:

- archivos `.env`;
- `secrets.env`;
- `.pem`;
- `.key`;
- tokens;
- passwords;
- URLs con credenciales;
- bases de datos;
- logs;
- certificados;
- dumps;
- backups.

Ejecuta comprobaciones que no revelen valores:

```bash
git status --short
git diff --cached --name-only
git check-ignore -v secrets.env .env 2>/dev/null || true
find . -type f \( -name '*.pem' -o -name '*.key' -o -name 'secrets.env' -o -name '.env' \) -print
```

Si encuentras un posible secreto:

1. no lo muestres;
2. no lo registres en `AGENTS.md`;
3. retíralo del staging;
4. comprueba si ya llegó a un commit;
5. marca el push como bloqueado;
6. informa únicamente del archivo y del tipo de riesgo.

Solo autoriza el push si la revisión termina sin hallazgos críticos.
