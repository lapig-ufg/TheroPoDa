![Vinícius Mesquita / DALEE - theropod, jurassic landscape, digital art, hight quality](Logo.jpg)

- ${\color{red}T} im {\color{red}e}\ Se {\color{red}r} ies\ Extracti {\color{red}o} n\ for\ {\color{red}Po} lygonal\ {\color{red}Da} ta\ and\ Trend\ Analysis\$ 
  ===========
[![GitLab license](./docs/mit.svg)](./LICENSE)

### Name
- 🦖T(h)eroPoDa+ - Time Series Extraction for Polygonal Data and Trend Analysis ⬛

### Description
- Toolkit created to extract median NDVI Time Series from Sentinel 2 data 🛰 stored in Google Earth Engine, perform gap filling and trend analysis [![image](https://user-images.githubusercontent.com/13785909/209228496-9fe31adc-a7cb-47c3-b476-64d82541f139.png)](https://earthengine.google.com/)

### Author
- Vinícius Vieira Mesquita - vinicius.mesquita@ufg.br (Main Theropoda)
### Co-author
- Leandro Leal Parente - leal.parente@gmail.com (Gap Filling and Trend Analysis implementation)

### Version
- 2.0.0

### Requirements (installation order from top to bottom)
- Python 3.10
- GDAL
- Rasterio 
- Pandas
- Geopandas
- Scikit-learn
- Joblib
- Psutil
- Statsmodels 
- [scikit-map](https://github.com/openlandmap/scikit-map)
- [Earthengine-api](https://developers.google.com/earth-engine/guides/python_install)

### How to use

- In this version of TheroPoDa (v2), you could extract a series of median NDVI from Sentinel 2, Landsat 8 and 9 for a Feature Collection of polygons simplily by passing arguments to the python code exemplified below.
- Also, a trend analysis is performed considering a time-series gap-filling (apllied to observations with less than 70% of usable pixels), a time series decomposition and a ordinary least square regression over series trend.

## ${\color{red} T(h)eroPoDa\ is\ HUNGRY\, she\ gonna\ "eat"\ all\ the\ data\ of\ EE\ and\ store\ it\ in\ her\ .db\ "belly"\ (SQLite\ file\ recognized\ by\ the\ .db\ extension)\ \}$

| argument                  | usage                                                                              | example  |
|:---------------------------------:|:----------------------------------------------------------------------------------:|:---------|
| --asset or -a             | Choosed Earth Engine Vector Asset                                                  | users/vieiramesquita/LAPIG_FieldSamples/lapig_goias_fieldwork_2022_50m |
| --id_field or -id         | Vector column used as ID (use unique identifiers!)                                 | ID_POINTS |
| --output_name or -o       | Output filename                                                                    | LAPIG_Pasture_S2_NDVI_Monitoring_FieldWork |
| --start_date or -start    | Start date baseline for the time series decomposition                              | 2019-01-01 |
| --end_date or -end        | End date baseline for the time series decomposition                                | 2025-01-01 |
| --window or -w            | Size of the time series standadization window (Default is 15 - average of 15 days) | 15 |
| --collection or -c        | The used satellite collection                                                      | Only Landsat or Sentinel (MODIS MOD13Q1 will be added soon) |

If you don't know how to upload your vector data in Earth Engine, you can follow the tutorial [clicking this link.](https://developers.google.com/earth-engine/guides/table_upload)

#### Command line example
```bash
python main.py -a users/vieiramesquita/LAPIG_FieldSamples/lapig_goias_fieldwork_2022_50m -id ID_POINTS -o LAPIG_Pasture_S2_NDVI_Monitoring_FieldWork -c Sentinel -start 2019-01-01 -end 2025-01-01 -w 15
```
### Roadmap

- Implement arguments to choose other zonal reducers (i.e. percentile, variance, etc.)
- Implement arguments to choose other satellite data series (i.e. more Landsat series, MODIS products)
- Implement a visualization of the processed data (or samples of it)
