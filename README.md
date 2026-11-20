# Precio de arte en Colombia

Proyecto local para investigar qué características permiten predecir el **precio de martillo o remate en COP nominales por lote adjudicado**, sin comisión del comprador.

La base original contiene **1.838 ventas, 61 columnas y 28 subastas**. El objetivo es demostrar capacidad predictiva fuera del entrenamiento. El repositorio inicial todavía no acredita un modelo de alto rendimiento.

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

Una vez instalado el extra `ml`:

```powershell
.\.venv\Scripts\python.exe run.py train --profile intrinseco --run-name intrinseco_01
.\.venv\Scripts\python.exe run.py train --profile sin_artista --run-name sin_artista_01
.\.venv\Scripts\python.exe run.py train --profile documentado --run-name documentado_01
```

Estos comandos comparan Ridge y Random Forest sobre `log1p(precio)`, guardan el candidato con menor MAE de validación y calculan importancia por permutación en esa partición. No ejecutan la prueba final. `--quick` sirve para una comprobación breve.

El perfil `con_avaluo` añade precios de salida y estimados: responde a un escenario diferente que ya conoce una valoración previa. El perfil predeterminado los excluye. Tampoco usa URLs, IDs de lote/subasta, controles ni estados posteriores a la venta.

| Partición | Fechas | Función |
| --- | --- | --- |
| Entrenamiento | Hasta 2024 | Ajustar el preprocesamiento y los modelos. |
| Validación | 2025 | Comparar candidatos y variables. |
| Prueba reservada | Desde 2026 | Evaluar la versión elegida al finalizar el desarrollo. |

Después de congelar las decisiones metodológicas, la prueba se abre de forma explícita:

```powershell
.\.venv\Scripts\python.exe run.py evaluate-test --run intrinseco_01
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
| `tests/` | Pruebas de datos, separación, features y modelos. |
| `.github/workflows/tests.yml` | Pruebas automáticas preparadas para el futuro remoto. |

Consulta la [metodología](docs/metodologia_modelado.md), el [plan de desarrollo](docs/plan_desarrollo.md), la [ficha de datos](docs/datos.md) y los [pasos para GitHub](docs/github.md).

La muestra describe subastas de Bogotá, con artistas colombianos y extranjeros. No representa todo el mercado colombiano ni las ventas directas de artistas emergentes. Los indicadores documentales conservan separado lo desconocido del cero explícito. Las dimensiones no se interpretan automáticamente como alto, ancho o profundidad.
