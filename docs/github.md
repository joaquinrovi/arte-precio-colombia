# Conectar el repositorio con GitHub

El repositorio se prepara primero de forma local, en la rama `main`. No es necesario crear un remoto para trabajar, ejecutar pruebas o guardar commits.

## Antes de crear el remoto

1. Elegir el propietario, el nombre y la visibilidad del repositorio en GitHub.
2. Crear un repositorio vacío, sin README, licencia ni `.gitignore` adicionales, para mantener el historial local como punto de partida.
3. Revisar los archivos que se publicarán con `git ls-files`. El Excel original, las tablas procesadas, el entorno virtual y los artefactos e informes locales de entrenamiento deben permanecer excluidos. El cotizador incluye un JSON con los parámetros necesarios para ejecutar la predicción en el navegador.

La configuración inicial no concede una licencia de redistribución a las páginas consultadas ni a los datos recopilados. El código y los datos requieren decisiones de licencia separadas; no se ha elegido una licencia abierta en nombre del propietario.

## Conectar y subir cuando esté decidido

Desde la carpeta del proyecto, sustituir `TU_USUARIO` y `TU_REPOSITORIO` por los valores reales:

```powershell
git status
git remote -v
git remote add origin https://github.com/TU_USUARIO/TU_REPOSITORIO.git
git push -u origin main
```

Si `origin` ya existe, revisar su dirección antes de ejecutar cambios; no añadirlo de nuevo ni sobrescribir una conexión existente sin comprobarla. La autenticación se realiza con el mecanismo de GitHub configurado en el equipo. No guardar tokens, contraseñas o claves privadas dentro del repositorio.

## Continuar trabajando

```powershell
git status
git add ruta/al/archivo
git diff --cached
git commit -m "Describe el cambio y su propósito"
git push
```

Los colaboradores deberán obtener por una vía autorizada el archivo de datos utilizado y comprobar su huella antes de reproducir una ejecución. El repositorio documenta la procedencia y la preparación, aunque esos archivos no se distribuyan mediante Git.
