![Vinícius Mesquita / DALEE - theropod, jurassic landscape, digital art, hight quality](Logo.jpg)

# 

- ${\color{red}T} im {\color{red}e}\ Se {\color{red}r} ies\ Extracti {\color{red}o} n\ for\ {\color{red}Po} lygonal\ {\color{red}Da} ta$

### Name
- T(h)eroPoDa + - Time Series Extraction for Polygonal Data and Trend Analysis ⬛

### Description
- Toolkit created to extract Time Series information from Sentinel 2 🛰 data stored in Earth Engine, gap filling and trend analysis [![image](https://user-images.githubusercontent.com/13785909/209228496-9fe31adc-a7cb-47c3-b476-64d82541f139.png)](https://earthengine.google.com/)

### Author
- Vinícius Vieira Mesquita - vinicius.mesquita@ufg.br (Main Theropoda)
### Co-author
- Leandro Leal Parente - leal.parente@gmail.com (Gap Filling and Trend Analysis implementation)

### Version
- 1.1.0

### Requirements (installation order from top to bottom)
- Python 3.10
- GDAL
- Rasterio 
- Pandas
- Geopandas
- Scikit-learn
- Joblib
- Psutil
- [scikit-map](https://pages.github.com/)

### How to use

- In this version of TheroPoDa (1.1.0), you could extract a series of median NDVI from Sentinel 2 for a Feature Collection of polygons simplily by passing arguments to the python code exemplified below:

| argument      | usage                                               | example  |
|:-------------:|:--------------------------------------------------: |:---------|
| --asset         | Choosed Earth Engine Vector Asset                   | users/vieiramesquita/LAPIG_FieldSamples/lapig_goias_fieldwork_2022_50m |
| --id_field      | Vector column used as ID (use unique identifiers!) | ID_POINTS |
| --output_name   | Output filename                                     | LAPIG_Pasture_S2_NDVI_Monitoring_FieldWork |

```bash
python theropoda.py --asset users/vieiramesquita/LAPIG_FieldSamples/lapig_goias_fieldwork_2022_50m --id_field ID_POINTS --output_name LAPIG_Pasture_S2_NDVI_Monitoring_FieldWork
```

If you don't know how to upload your vector data in Earth Engine, you can follow the tutotial [clicking this link.](https://developers.google.com/earth-engine/guides/table_upload)

### Roadmap

- Implement arguments to choose other zonal reducers (i.e. percentile, variance, etc.)
- Implement arguments to choose other satellite data series (i.e. Landsat series, MODIS products)
- Implement a visualization of the processed data (or samples of it)
