# Metodología del modelo de precios

El objetivo es estimar `precio_venta_cop`, el precio de martillo o remate publicado de un lote adjudicado. Se expresa en pesos colombianos nominales de la fecha de subasta y excluye la comisión del comprador. Una adjudicación publicada no demuestra el pago ni la entrega de la obra.

## Alcance de los datos

La versión inicial del Excel contiene 1.838 adjudicaciones, 61 columnas y 28 subastas de 2020 a 2026. De ellas, 1.631 tienen la marca `usar_modelo_base = 1` de la recopilación. Esa marca es un filtro inicial de calidad; no certifica que una ficha esté libre de errores.

La muestra procede del mercado de subastas en Bogotá e incluye artistas colombianos y extranjeros. No representa las ventas directas de artistas, los encargos ni el conjunto de galerías colombianas. La validación y la prueba recientes contienen únicamente Bogotá Auctions, mientras que Lefebre aparece en años anteriores. Los resultados deberán describirse dentro de ese alcance.

Cada fila corresponde a un lote. Un conjunto de piezas tiene un precio conjunto y no permite inferir el precio de cada obra. Las dimensiones conservan el orden de la fuente: `dim1_cm` y `dim2_cm` no equivalen automáticamente a alto y ancho. El área rectangular es un descriptor geométrico y no la superficie material real de la pieza.

El precio todavía no está ajustado por inflación. Cualquier transformación a pesos constantes deberá registrar la serie utilizada, la fecha base y la regla de unión, manteniendo intacto el precio original.

## Preparación y selección inicial

1. Conservar el Excel original y registrar su huella SHA-256.
2. Validar identificadores, moneda COP, target positivo, fechas y dimensiones.
3. Aplicar el filtro de calidad configurado y registrar cuántas filas excluye cada regla.
4. Excluir por defecto la subasta 2694, del 19 de noviembre de 2026, porque su posventa estaba abierta al recopilar los resultados. La opción debe quedar explícita en la configuración.
5. Conservar los faltantes como información desconocida. Una mención documental con valor `1`, un valor explícito `0` y un campo vacío son estados distintos.
6. Conservar posibles reventas o ejemplares distintos. Una coincidencia de artista, título, año y medidas genera una revisión, no una eliminación automática.

No se deducen estilo, tema, autenticidad, orientación, marco o peso cuando la fuente no los documenta. Las fechas biográficas y los años de obra pueden contener errores del catálogo; no se corrigen mediante suposiciones.

## Particiones temporales

| Partición | Fechas de subasta | Uso |
| --- | --- | --- |
| Entrenamiento | Hasta el 31 de diciembre de 2024 | Ajustar parámetros, imputación, escalado y codificación. |
| Validación | Del 1 de enero al 31 de diciembre de 2025 | Comparar modelos, perfiles de variables y decisiones de selección. |
| Prueba final | Desde el 1 de enero de 2026 | Evaluar una versión congelada después de cerrar las decisiones anteriores. |

Una fecha de subasta completa debe permanecer en una sola partición. Los conteos definitivos se obtienen después de aplicar los filtros configurados; no se fijan a mano a partir del total del Excel.

Las etiquetas de precio de la prueba final no se consultan para elegir variables, ajustar hiperparámetros ni calcular importancia por permutación. La inspección de su esquema y cobertura no autoriza a utilizar sus resultados para iterar el modelo. Las filas o posibles obras repetidas entre particiones se informan para valorar el alcance de la independencia temporal.

Se distinguirá entre artistas vistos durante el entrenamiento y artistas nuevos. Un resultado agregado favorable puede ocultar un rendimiento pobre en estos últimos. El conjunto de prueba contiene pocas fechas de subasta y no permite afirmar generalización a todas las casas o a artistas emergentes.

## Perfiles de variables

| Perfil | Contenido y propósito |
| --- | --- |
| `intrinseco` | Identidad del artista, técnica, soporte, tipo de objeto, dimensiones, información de edición y fechas disponibles al predecir. Es el punto de partida. |
| `sin_artista` | El mismo enfoque sin identidad del artista. Permite medir cuánto depende la predicción de conocer al autor. |
| `documentado` | Añade menciones de firma, certificado, procedencia, literatura o exposición, conservando la distinción entre vacío y valor explícito. |
| `con_avaluo` | Añade precio de salida o estimados publicados antes de la venta. Responde a un escenario que ya dispone de una valoración previa y se informa por separado. |

La identidad del artista es una categoría legítima si está disponible al solicitar la predicción. Los identificadores de registro, subasta y lote, las URLs, los estados posteriores a la venta y los controles de calidad quedan fuera de las entradas. El texto identificador original también queda fuera: puede mezclar biografías, fechas y contenido asociado al resultado.

La selección se implementa mediante una lista explícita de columnas. Agregar una nueva columna al archivo de datos no debe incorporarla automáticamente al modelo.

## Modelos y métricas

La referencia funcional compara una mediana global con una estimación por artista regularizada hacia la población. La regularización reduce la influencia de artistas con pocas observaciones. Los artistas no vistos deben tener una respuesta de respaldo definida usando solo entrenamiento.

La comparación opcional con scikit-learn incluye Ridge y Random Forest con transformación `log1p` del precio y retorno a COP mediante la transformación inversa. Imputación, codificación y escalado se ajustan dentro del pipeline usando únicamente el entrenamiento. Las categorías inéditas deben admitirse sin romper la predicción.

El comando `benchmark` ordena los modelos por MAE de validación en COP. También informa mediana del error absoluto, RMSE, RMSLE, R², mediana del error porcentual absoluto y porcentaje de predicciones a menos de 25 % o exactamente 25 % del precio observado. RMSE da mayor peso a errores grandes, mientras que la mediana indica el error típico. R² mide el ajuste en la escala original de los precios y puede tomar valores negativos.

La comparación ejecuta un modelo aditivo con splines, KNN ponderado y Gradient Boosting de árboles poco profundos con NumPy y pandas. Con scikit-learn disponible añade Ridge, Random Forest, Extra Trees, Gradient Boosting con pérdida Huber y SVR. Los hiperparámetros de esta corrida inicial se fijan antes de comparar errores. El informe conserva el desglose por fecha y por artista conocido o nuevo para el ganador.

## Identificación de variables útiles

La importancia por permutación se calcula en validación sobre las columnas de entrada del modelo, no sobre el conjunto de prueba final. Mide cuánto empeora una métrica cuando se altera una variable. Su interpretación depende del modelo entrenado y de la muestra utilizada.

El cuadro de `benchmark` agrupa las variables relacionadas. Cada repetición reordena juntas las columnas del grupo, por ejemplo dimensiones, área y proporción, y registra cuánto cambia el MAE. La dispersión entre permutaciones indica sensibilidad de esta medición en la muestra disponible.

Se comparará también el rendimiento al retirar grupos: artista, geometría, fechas, edición y documentación. Esta comparación es necesaria porque dimensiones, área y relación de lados están relacionadas: una variable puede parecer poco importante cuando otra contiene información similar.

Los rankings y las ablaciones son resultados exploratorios de validación. No prueban causalidad ni justifican eliminar automáticamente una variable. Después de decidir el perfil y el modelo, se congela la configuración y se utiliza la prueba final una sola vez para esa versión.

## Experimento con fichas de galería

La corrida `galeria_2026_11_20` usa fichas consultadas el 20 de noviembre de 2026 de [La Galería Online](https://lagaleriaonline.co/collections/obras). El objetivo `precio_publicado_cop` es el valor anunciado en pesos colombianos en cada ficha consultada. La disponibilidad se conserva como dato de auditoría. En caso de precios incompatibles para un mismo producto se excluyen esas observaciones. El año de creación se registra a partir del primer año indicado en las fichas recuperadas y puede corresponder al inicio de un intervalo.

Se reunieron 642 registros de páginas de producto, que incluyen algunas consultas repetidas. Tras validar técnica, precio, artista y medidas de la obra, quedaron 335 fichas de 67 artistas. Hay 45 obras al óleo, 16 a grafito y 19 a lápiz sin especificación de grafito. Las medidas comparables son las de la obra en centímetros. La base local conserva las URLs, medidas y técnicas originales y un manifiesto SHA-256. Las fichas corresponden a una sola galería, con una muestra de páginas indexadas y búsquedas enfocadas en las técnicas de Encargos.

Se reservaron 66 fichas de 13 artistas para prueba, incluidas 22 fichas de óleo o grafito. Sobre las 269 fichas restantes se probaron 54 configuraciones con cinco particiones agrupadas por artista. El criterio de selección fue el error absoluto medio (MAE) en COP para óleo y grafito en validación cruzada. Los modelos pueden aprender de otras técnicas de la galería durante el ajuste. El nombre del artista se usa para dividir las fichas y queda fuera del cálculo del precio.

| Configuración elegida por familia | MAE validación cruzada (COP) | MAE prueba reservada (COP) | R² en prueba |
| --- | ---: | ---: | ---: |
| Aditivo regularizado | 2.284.450 | 1.428.119 | −0,239 |
| Gradient Boosting | 2.312.574 | 1.462.813 | −0,281 |
| KNN ponderado | 2.406.156 | 1.306.007 | −0,184 |
| Mediana global | 3.162.828 | 1.500.000 | −0,474 |
| Mediana por técnica | 3.795.826 | 1.440.909 | −0,246 |

El modelo aditivo fue seleccionado antes de abrir la prueba. La penalización óptima fue 12 dentro de la cuadrícula y la configuración eligió cero nudos. En permutación sobre validación, el MAE subió $747.302 COP al desordenar dimensiones (área y proporción), $311.711 COP para año y $10.880 COP para técnica. El soporte se probó como entrada adicional y quedó fuera de la configuración elegida.

La prueba de óleo dio un MAE de $245.971 COP en 10 fichas de cuatro artistas. La validación cruzada de óleo dio $2.467.422 COP, lo que muestra la sensibilidad a los artistas evaluados. En grafito, el MAE de prueba fue $2.413.242 COP en 12 fichas de tres artistas y superó el error de ambas medianas. El cotizador muestra la referencia experimental de galería para óleo en medidas cubiertas. Usa el año actual para una obra nueva. El valor estima un precio anunciado de galería y puede orientar una propuesta de encargo. [Probar en Encargos](https://joaquinrovi.github.io/arte-precio-colombia/cotizador/encargos/)

### Reproducir el entrenamiento

Ejecuta desde la raíz. Los CSV de entrada, el catálogo preparado, los informes y los parámetros generados son archivos locales ignorados por Git.

```powershell
.\.venv\Scripts\python.exe scripts/prepare_gallery_catalog.py --input data/raw/galeria_cobertura_piloto.csv data/raw/galeria_cobertura_ampliada.csv data/raw/galeria_fichas_dirigidas.csv --output data/processed/galeria_catalogo_2026-11-20.csv --consulted-at 2026-11-20
.\.venv\Scripts\python.exe scripts/train_gallery_model.py --input data/processed/galeria_catalogo_2026-11-20.csv --run galeria_revision --checked-at 2026-11-20
```

El archivo `reports/runs/galeria_2026_11_20/metrics.json` contiene el desglose de la corrida original. El navegador usa `docs/cotizador/encargos/gallery-model.json` con los coeficientes, los parámetros de transformación y los límites de cobertura para óleo. Para probarlo localmente, sirve `docs/` por HTTP y abre [Encargos](http://127.0.0.1:8000/cotizador/encargos/).

## Referencias técnicas

- [scikit-learn: errores frecuentes y prevención de contaminación de datos](https://scikit-learn.org/stable/common_pitfalls.html).
- [scikit-learn: importancia de variables por permutación](https://scikit-learn.org/stable/modules/permutation_importance.html).
- [scikit-learn: pipelines y estimadores compuestos](https://scikit-learn.org/stable/modules/compose.html).
