# Trabajo en este repositorio

- Leer README.md, configs/default.toml y docs/metodologia_modelado.md antes de cambiar el flujo.
- Mantener intacto el Excel de data/raw/. Registrar cualquier cambio de versión de datos con su huella.
- Usar una lista explícita de features. No incorporar target, IDs de registro/subasta/lote, URLs ni estados posteriores a la venta como predictores.
- Mantener `con_avaluo` separado del escenario que no conoce precios de salida o estimados.
- Ajustar imputación, codificación y escalado solo con entrenamiento. Elegir variables y parámetros con validación, conservando la prueba final para una versión congelada.
- No eliminar posibles reventas solo por artista y título ni confundir faltantes documentales con un NO.
- Ejecutar las pruebas desde la raíz con `PYTHONPATH=src python -m unittest discover -s tests -v`; en PowerShell fijar `$env:PYTHONPATH = "src"` antes. Revisar skips de las dependencias opcionales.
- Preparación local: `python run.py prepare`; validación: `python run.py validate`; referencia: `python run.py baseline`.
- Mantener datos, modelos, resultados generados, entornos y credenciales fuera del seguimiento de Git según .gitignore.
- Informar lo que se ejecutó y lo que quedó sin verificar. No presentar un scaffold o una métrica de entrenamiento como rendimiento predictivo validado.
