# Verificación inicial del repositorio

Fecha: 20 de noviembre de 2026. Esta comprobación valida el flujo inicial; no constituye una evaluación final de capacidad predictiva.

- Excel original: 1.838 ventas y 61 columnas; huella registrada en `data/dataset_manifest.json`.
- Filas seleccionadas por la configuración inicial: 1.611. Se mantiene intacto el archivo original.
- Entrenamiento: 1.177 filas, 21 fechas de subasta, hasta 2024.
- Validación: 255 filas, 4 fechas de subasta en 2025.
- Prueba reservada: 179 filas, 2 fechas de subasta de 2026. No se calcularon sus errores.
- Pruebas del núcleo: 14 correctas.
- Pruebas opcionales de scikit-learn: 4 omitidas por dependencia no instalada.

## Referencias de validación ejecutadas

| Referencia | MAE (COP) | Mediana del error absoluto (COP) | RMSLE |
| --- | ---: | ---: | ---: |
| Mediana global | 10.808.235 | 3.000.000 | 1,287 |
| Mediana por artista suavizada | 9.826.445 | 2.700.000 | 1,119 |

Ambas referencias se ajustaron únicamente en entrenamiento. Estos errores son el punto de comparación para los modelos posteriores; todavía son elevados y no justifican presentar el proyecto como un predictor preciso. Los resultados completos y las predicciones de la ejecución `referencia_inicial` permanecen en `reports/runs/`, fuera del seguimiento de Git.

Entorno comprobado: Python 3.12.14, NumPy 2.3.5, pandas 3.0.1 y openpyxl 3.1.5. No se ejecutaron Ridge ni Random Forest en este entorno. El workflow preparado para GitHub instala el extra `ml` y ejecuta también las pruebas de esos modelos cuando se publique el repositorio.
