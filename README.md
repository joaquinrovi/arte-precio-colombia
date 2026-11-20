# Precio de arte en Colombia

Proyecto para investigar qué características permiten predecir el **precio de martillo o remate en COP nominales por lote adjudicado**, sin comisión del comprador.

La base original contiene **1.838 ventas, 61 columnas y 28 subastas**. El proyecto evalúa la capacidad predictiva en ventas posteriores a las de entrenamiento.

## Cotizador web

[Abrir el cotizador](https://joaquinrovi.github.io/arte-precio-colombia/cotizador/)

Estima en COP el **precio de remate** de un lote adjudicado en subastas de Bogotá, antes de la comisión del comprador. Es una referencia experimental para ese mercado. Los encargos, los honorarios de un artista y las ventas directas quedan fuera de la muestra.

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

Sirve `docs/` mediante HTTP y abre [localhost:8000/cotizador/](http://localhost:8000/cotizador/).

```powershell
python -m http.server 8000 --directory docs --bind 127.0.0.1
```

Para regenerar `model.json` desde la corrida local congelada y comprobar la paridad con Python, ejecuta desde la raíz con el entorno Python del proyecto y Node.js disponibles.

```powershell
.\.venv\Scripts\python.exe scripts/export_web_model.py --run benchmark_2025_verificado --check-parity
node --test tests/test_web_prediction.mjs
```

GitHub Pages publica la carpeta `docs/` de la rama `main`.

## Empezar en este equipo

El entorno `.venv` ya está creado y el Excel está en `data/raw/`. Desde esta carpeta, en PowerShell:

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

En el entorno de preparación actual no se pudo instalar scikit-learn. Funcionan preparación, validación, referencias y pruebas del núcleo; los modelos opcionales esperan esas dependencias. El entorno local reutiliza las bibliotecas del runtime instalado mediante `--system-site-packages`; una instalación nueva puede ser independiente.

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
| `docs/cotizador/` | Formulario estático y motor de inferencia en JavaScript. |
| `tests/` | Pruebas de datos, separación, features, modelos e inferencia web. |
| `.github/workflows/tests.yml` | Pruebas automáticas en GitHub Actions. |

Consulta la [metodología](docs/metodologia_modelado.md), el [plan de desarrollo](docs/plan_desarrollo.md), la [ficha de datos](docs/datos.md) y los [pasos para GitHub](docs/github.md).

La muestra describe subastas de Bogotá, con artistas colombianos y extranjeros. No representa todo el mercado colombiano ni las ventas directas de artistas emergentes. Los indicadores documentales conservan separado lo desconocido del cero explícito. Las dimensiones no se interpretan automáticamente como alto, ancho o profundidad.
