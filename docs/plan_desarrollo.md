# Plan de desarrollo

El repositorio permite avanzar desde la base documentada hasta una evaluación predictiva reproducible. La calidad se demostrará mediante resultados fuera del entrenamiento; no se presupone un rendimiento alto por elegir un algoritmo más complejo.

## 1. Consolidar la versión inicial

- Importar el Excel original sin sobrescribirlo y registrar su huella.
- Verificar el esquema, los precios COP y los filtros de calidad.
- Revisar fichas contradictorias, alias de artistas y lotes conjuntos.
- Generar una tabla procesada y un registro de exclusiones reproducibles.

**Criterio de cierre:** cualquier persona con el archivo de origen y las dependencias puede reconstruir las filas admitidas y explicar cada exclusión.

## 2. Analizar cobertura y calidad

- Medir faltantes por variable, año y casa de subastas.
- Revisar la distribución de precios, técnicas, tamaños y observaciones por artista.
- Separar ausencia documental de información no publicada.
- Identificar posibles reventas, ediciones repetidas y cambios de cobertura entre años.
- Estudiar qué submercados están suficientemente representados.

**Criterio de cierre:** disponer de un informe que delimite las obras y condiciones para las que resulta razonable experimentar. Esta fase todavía no elige variables a partir de la prueba final.

## 3. Establecer referencias

- Fijar entrenamiento hasta 2024, validación en 2025 y prueba reservada desde 2026.
- Comparar mediana global y estimación por artista regularizada.
- Registrar métricas y errores de validación por artista conocido o nuevo.
- Conservar configuración, semilla, versión de datos y versión de código.

**Criterio de cierre:** tener una referencia reproducible que los modelos posteriores puedan superar en el mismo conjunto de validación.

## 4. Comparar modelos y variables

- Ejecutar Ridge y Random Forest cuando las dependencias estén instaladas.
- Comparar los perfiles `intrinseco`, `sin_artista`, `documentado` y `con_avaluo`.
- Calcular importancia por permutación y ablaciones en validación.
- Revisar estabilidad frente a semillas y grupos de variables correlacionadas.
- Ajustar hiperparámetros exclusivamente con datos de desarrollo.

**Criterio de cierre:** seleccionar un candidato por evidencia de validación y por su comportamiento en casos relevantes, dejando documentados sus límites. El perfil con avalúo previo se compara como un escenario diferente.

## 5. Evaluación final y uso

- Congelar variables, filtros, transformaciones, hiperparámetros y métricas.
- Evaluar la versión congelada sobre la prueba temporal reservada.
- Analizar los errores e informar el alcance de las pocas fechas disponibles.
- Definir cuándo una obra queda fuera de la cobertura conocida.
- Diseñar intervalos de predicción y calibrarlos con una partición adecuada en una fase posterior.

**Criterio de cierre:** una ficha del modelo describe datos, fecha de corte, resultados, supuestos y condiciones de uso. Si el rendimiento no mejora la referencia, se conserva ese resultado y se vuelve a estudiar los datos sin presentar el experimento como un predictor validado.

## Seguimiento en Git

Cada cambio metodológico debe acompañarse de un commit que explique el cambio y su verificación. Los archivos de resultados generados permanecen fuera del seguimiento de Git; los hallazgos relevantes pueden resumirse en documentos revisados, con el identificador de la ejecución correspondiente.

La publicación futura en GitHub empieza por el código y la documentación. La incorporación de archivos de origen o datos derivados requiere revisar por separado las condiciones de las fuentes y decidir qué se puede distribuir. La disponibilidad pública de una página no aporta por sí sola una licencia de redistribución al conjunto recopilado.
