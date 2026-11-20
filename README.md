# Precio de arte en Colombia

Proyecto para estudiar el precio de remate de obras de arte en subastas de Bogotá. El cotizador web también ayuda a preparar encargos con tarifas publicadas por proveedores en Colombia, una referencia experimental de galería para óleo y una calculadora de costos.

La base original reúne **1.838 lotes adjudicados de 28 subastas** y contiene **61 columnas**. La evaluación de Remates usa lotes de subastas posteriores a las de entrenamiento.

## Cotizador web

[Abrir el cotizador](https://joaquinrovi.github.io/arte-precio-colombia/cotizador/)

### Precios de referencia para encargos

Selecciona **Óleo** o **Grafito**, elige el tipo de encargo e indica las medidas en centímetros. Pulsa **Buscar precios** para consultar las referencias o **Limpiar** para empezar otra consulta. [Abrir Encargos](https://joaquinrovi.github.io/arte-precio-colombia/cotizador/encargos/)

| Resultado | Qué muestra | Cómo se suma el marco |
| --- | --- | --- |
| **Oferta de encargo** | Tarifa publicada de la medida más cercana por proveedor, con hasta 25 % de diferencia en cada lado. Puede incluir el plazo y el estado del marco. Un precio «desde» es un valor inicial. | El costo cotizado se suma cuando la medida es exacta y la oferta indica «Sin enmarcar». |
| **Referencia experimental de galería** | Estimación del precio de catálogo de La Galería Online para óleo en medidas cubiertas. El modelo predictivo usa el año actual para una obra nueva. | El costo cotizado se suma al precio base estimado. La tarjeta muestra el total orientativo con el desglose. |

Para probar el marco, elige **Óleo** y **Retrato de una figura humana**, escribe **60** de ancho, **80** de alto y **100000** en **Costo cotizado del marco (COP)**. Tras pulsar **Buscar precios**, la tarjeta de galería muestra **$3.062.641 COP** como total orientativo, con **$2.962.641 COP** de precio base estimado y **$100.000 COP** de marco.

El modelo de galería se estudió con 335 fichas de 67 artistas. El error en óleo varió según los artistas evaluados. Para retratos en grafito, el aplicativo muestra tarifas publicadas de encargo. Estos valores sirven para orientar una propuesta. [Evaluación del modelo de galería](docs/metodologia_modelado.md#experimento-con-fichas-de-galería)

### Presupuesto por costos

Si ya conoces cuánto quieres cobrar por hora, la calculadora suma tu tiempo y tus gastos. Funciona en el navegador. [Abrir presupuesto por costos](https://joaquinrovi.github.io/arte-precio-colombia/cotizador/encargos/costos/)

1. Suma los materiales consumidos, los gastos extra y las horas de trabajo multiplicadas por la tarifa por hora.
2. Si se indica una reserva para imprevistos, aplícala a esa suma.
3. Si el medio de cobro descuenta una comisión porcentual, aumenta el precio para cubrirla. Redondea el precio hacia arriba a un múltiplo de $1.000 COP.

Incluye ejemplos editables de óleo y grafito. Sus cifras ilustran el cálculo. El presupuesto refleja los supuestos de quien lo prepara y el precio final se acuerda con el cliente.

### Estimación de remate

El **remate** es el cierre de la puja en que se adjudica un lote a quien hizo la oferta ganadora. El **precio de martillo** es el valor de esa oferta antes de la comisión del comprador. El cotizador estima ese valor en COP para subastas de Bogotá. [Abrir Remates](https://joaquinrovi.github.io/arte-precio-colombia/cotizador/)

Puedes escribir cualquier nombre o dejar el campo de artista vacío. Un artista con suficiente historial activa su efecto dentro del modelo. Un artista nuevo o con un solo lote de entrenamiento recibe una estimación basada en las demás características. Guardar un nombre lo añade a las sugerencias de ese navegador. Para aprender un efecto propio se requieren ventas observadas y un nuevo entrenamiento.

El cotizador ejecuta en el navegador el modelo aditivo con splines de `benchmark_2025_verificado`. Técnica, soporte y tipo de obra, artista y dimensiones fueron los tres grupos de mayor aporte predictivo en la validación de 2025. El formulario permite añadir datos como año de la obra y tiraje. El cálculo se realiza localmente en el navegador y el sitio sirve solo los parámetros de inferencia y el catálogo de opciones.

### Resultados en la prueba temporal

El modelo, entrenado con datos hasta 2024, se eligió con los lotes de 2025. La prueba reservada de 2026 reunió 179 lotes de dos subastas de Bogotá Auctions.

| Grupo de lotes | Lotes | Error porcentual absoluto mediano | Estimaciones dentro de ±25 % |
| --- | ---: | ---: | ---: |
| Total | 179 | 54,0 % | 27,9 % |
| Con efecto de artista | 127 | 46,2 % | 33,1 % |
| Sin efecto de artista | 52 | 84,5 % | 15,4 % |
| De los anteriores, artistas ausentes del entrenamiento | 31 | 85,0 % | 19,4 % |

El MAE global fue de $7.762.911 COP y el R² fue de 0,192. Los porcentajes describen el error observado en esos lotes. La aplicación presenta una estimación puntual, con un aviso sobre el mayor error observado cuando el modelo carece de un efecto propio para el artista.

### Ejecutar y verificar localmente

El repositorio incluye los archivos que necesita el cotizador. Sirve `docs/` mediante HTTP y abre [localhost:8000/cotizador/](http://localhost:8000/cotizador/).

```powershell
python -m http.server 8000 --directory docs --bind 127.0.0.1
```

Para regenerar el `model.json` de Remates desde la corrida local congelada y comprobar la paridad con Python, ejecuta desde la raíz con el entorno Python del proyecto y Node.js disponibles.

```powershell
.\.venv\Scripts\python.exe scripts/export_web_model.py --run benchmark_2025_verificado --check-parity
node --test tests/test_web_prediction.mjs tests/test_commission_price.mjs tests/test_commission_comparables.mjs
```

GitHub Pages publica la carpeta `docs/` de la rama `main`.

## Preparar y validar los datos

Con el entorno `.venv` y el Excel original en `data/raw/`, ejecuta desde la raíz del repositorio en PowerShell:

```powershell
.\.venv\Scripts\python.exe run.py prepare
.\.venv\Scripts\python.exe run.py validate
.\.venv\Scripts\python.exe run.py baseline
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`prepare` valida la fuente, registra huellas SHA-256 y genera un CSV local. La configuración inicial selecciona **1.611 filas**: aplica `usar_modelo_base=1`, excluye conjuntos explícitos y las adjudicaciones cuya posventa seguía abierta. El Excel permanece intacto.

`baseline` compara mediana global y mediana por artista suavizada, ajustadas solo con entrenamiento. Genera métricas y predicciones **de validación**; conserva la prueba final reservada.

## Instalar en otro entorno

Requiere Python 3.11 o posterior. En un entorno con acceso a paquetes:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[ml,dev]"
```

Copia el Excel original en `data/raw/Base_arte_Colombia_v1.xlsx` y comprueba su huella contra [el manifiesto](data/dataset_manifest.json). Los datos originales y procesados están fuera de Git. El diccionario de columnas y la documentación sí están versionados.

## Comparar modelos y variables

Ejecuta la comparación desde la raíz del repositorio.

```powershell
.\.venv\Scripts\python.exe run.py benchmark --profile intrinseco
```

`benchmark` compara las medianas de referencia con un modelo aditivo con splines, KNN ponderado y Gradient Boosting de árboles poco profundos. Si scikit-learn está instalado, incorpora Ridge, Random Forest, Extra Trees, Gradient Boosting con pérdida Huber y SVR con kernel RBF. El informe registra los candidatos disponibles y los omitidos.

Los archivos locales de cada corrida incluyen `model_comparison.csv` con el ranking por MAE, `validation_by_auction.csv` con el desglose por subasta y `group_importance_validation.csv` con el cambio de MAE al permutar grupos de variables. El comando guarda el modelo ganador y las predicciones de validación. La opción `--quick` reduce el número de iteraciones para comprobar el flujo.

Los perfiles `sin_artista` y `documentado` permiten repetir el experimento con otras variables. `train` conserva el flujo original de Ridge y Random Forest para comparaciones anteriores.

El perfil `con_avaluo` añade precios de salida y estimados: responde a un escenario diferente que ya conoce una valoración previa. El perfil predeterminado los excluye. Tampoco usa URLs, IDs de lote/subasta, controles ni estados posteriores a la venta.

| Partición | Fechas | Función |
| --- | --- | --- |
| Entrenamiento | Hasta 2024 | Ajustar el preprocesamiento y los modelos. |
| Validación | 2025 | Comparar candidatos y variables. |
| Prueba reservada | Desde 2026 | Evaluar la versión elegida al finalizar el desarrollo. |

Después de congelar las decisiones metodológicas, la prueba se abre de forma explícita:

```powershell
.\.venv\Scripts\python.exe run.py evaluate-test --run NOMBRE_DE_LA_CORRIDA
```

Ese resultado deja de ser independiente si después se utiliza para ajustar el modelo. La importancia de una variable es exploratoria, depende del modelo y no prueba causalidad.

### Buscar hiperparámetros de splines

El comando `tune-spline` prueba 32 combinaciones de penalización y cantidad de nudos por variable numérica. Usa ventanas anuales crecientes dentro del entrenamiento y elige el menor MAE por lote. Con la configuración predeterminada, las ventanas puntúan subastas de 2021 a 2024. Después se ajustan ambas configuraciones con los datos hasta 2024 y se comparan en 2025. Esa comparación es retrospectiva porque 2025 ya sirvió para escoger la familia del modelo.

```powershell
.\.venv\Scripts\python.exe run.py tune-spline --profile intrinseco
```

La corrida local guarda `spline_grid.csv`, `spline_by_year.csv`, `validation_comparison.csv`, `validation_by_auction.csv` y `metrics.json`. Este último también desglosa el error para artistas presentes y ausentes en el entrenamiento. El comando guarda la configuración ajustada y su modelo para reproducir el experimento. La evaluación de prueba y la publicación en web son pasos separados.

## Organización

| Ruta | Contenido |
| --- | --- |
| `src/arte_precio/` | Preparación, features, particiones, referencias, métricas y modelos. |
| `configs/default.toml` | Fuente, filtros, fechas, perfil y semilla. |
| `data/raw/` | Excel original local, ignorado por Git. |
| `data/processed/` | CSV y manifiesto generados, ignorados por Git. |
| `data/dictionary.json` | Definiciones de las columnas originales. |
| `reports/runs/` | Métricas y predicciones de cada experimento local. |
| `artifacts/` | Modelos y parámetros de cada experimento local. |
| `docs/cotizador/` | Formularios de Remates y Encargos, con parámetros de inferencia y catálogo de ofertas. |
| `scripts/` | Preparación y entrenamiento del modelo de galería y exportación del modelo web de Remates. |
| `tests/` | Pruebas de datos, separación, features, modelos e inferencia web. |
| `.github/workflows/tests.yml` | Pruebas automáticas en GitHub Actions. |

Consulta la [metodología](docs/metodologia_modelado.md), el [plan de desarrollo](docs/plan_desarrollo.md), la [ficha de datos](docs/datos.md) y los [pasos para GitHub](docs/github.md).

La muestra describe subastas de Bogotá, con artistas colombianos y extranjeros. No representa todo el mercado colombiano ni las ventas directas de artistas emergentes. Los indicadores documentales conservan separado lo desconocido del cero explícito. Las dimensiones no se interpretan automáticamente como alto, ancho o profundidad.
