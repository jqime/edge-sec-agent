# REVISIÓN FINAL, COMMIT Y PUSH

No hagas commit todavía. Primero realiza una revisión final.

Ejecuta:

```bash
git status --short
git diff --check
git diff --stat
git diff
```

Comprueba que:

- no hay secretos;
- no hay bases de datos;
- no hay logs;
- no hay certificados privados;
- no hay archivos generados;
- no se han eliminado funcionalidades;
- no se han cambiado endpoints incompatiblemente;
- los tests pasan;
- `AGENTS.md` está actualizado;
- la Orange Pi está documentada con evidencia real.

Lista exactamente los archivos modificados por esta sesión.

Añade solo esos archivos concretos:

```bash
git add AGENTS.md
git add <archivo-1>
git add <archivo-2>
```

No uses `git add .` ni `git add -A`.

Revisa el staging:

```bash
git diff --cached --name-only
git diff --cached --check
git diff --cached --stat
```

Si hay un archivo inesperado, detente.

Después crea un commit:

```bash
git commit -m "chore: rebuild and validate Orange Pi deployment"
```

Verifica:

```bash
git log -1 --oneline
git status --short
```

Haz push únicamente a la rama de trabajo:

```bash
git push -u origin "$(git branch --show-current)"
```

No hagas merge a `main`.

Actualiza `AGENTS.md` después del commit con:
- hash;
- rama;
- archivos incluidos;
- resultado del push;
- estado final.
