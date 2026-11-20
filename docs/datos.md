# Datos y procedencia

La fuente inicial es `Base_arte_Colombia_v1.xlsx`, recopilada el 20 de noviembre de 2026. Contiene 1.838 adjudicaciones en la hoja `Ventas`, 61 columnas y 28 subastas entre el 25 de marzo de 2020 y el 19 de noviembre de 2026.

El archivo completo conserva un diccionario, fuentes por lote, cobertura, metodología, registros sin precio y objetos excluidos. Este proyecto importa la hoja `Ventas`; no convierte los registros sin precio en ventas de valor cero.

Fuentes de resultados:

- [Archivo de Bogotá Auctions](https://www.bogotaauctions.com/es/subastas-historicas).
- [Lefebre Subastas en Auctionzip, ejemplo de catálogo](https://www.auctionzip.com/auction-catalog/subasta-18_MBOXTZYYUM).

Las URLs individuales se conservan en la fuente y en el CSV local para revisión. La publicación de resultados indica adjudicación, no una factura liquidada. El target es un precio nominal por lote, sin comisión, y los lotes conjuntos no tienen precios individuales de cada pieza.

El [manifiesto](../data/dataset_manifest.json) fija la huella del Excel utilizado. `prepare` vuelve a calcular esa huella y la del CSV, registra los filtros y conserva los faltantes. No requiere descargar nuevamente las páginas ni reproduce a ciegas una captura antigua de ellas.

La marca original `usar_modelo_base=1` admite 1.631 filas. La configuración predeterminada del repositorio selecciona 1.611 al excluir además las filas admitidas de la subasta cuya posventa seguía abierta. Estas cifras son un control de esta versión; se recalculan al cambiar la fuente o los filtros.

Existe al menos un valor explícito `firma_mencionada=0` en la fuente. Se conserva, sin convertir los campos vacíos en cero ni suponer que certifica la ausencia real de firma. El perfil `documentado` trata `1`, `0` y falta de información como categorías distintas.

Antes de publicar archivos de datos en un remoto, se debe decidir su distribución conforme a las condiciones de las fuentes. La configuración inicial mantiene Excel, CSV y resultados en el equipo, fuera de Git; compartir el código no publica esos archivos automáticamente.
