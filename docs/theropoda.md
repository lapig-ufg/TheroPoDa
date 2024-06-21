
# Theropoda Module

This module includes functionalities related to `theropoda.py` code.

## Overview

The `theropoda.py` module provides functions to extract time series information from Sentinel 2 data stored in Earth Engine.

#### Attributes

- `asset` (str): Choosed Earth Engine vector asset.
- `id_field` (str): Vector column used as ID (use unique identifiers!).
- `output_name` (str): Output filename.

#### Example Usage

```python

asset	= 'users/vieiramesquita/LAPIG_FieldSamples/lapig_goias_fieldwork_2022_50m'
id_field = 'ID_POINTS'
output_name = 'LAPIG_Pasture_S2_NDVI_Monitoring_FieldWork.csv'
```

## Functions

### 1.`getTimeSeries`

  This function is responsible to get the time series of Sentinel 2 data throught Earth Engine. It needs a `geometry` object in the `ee.Feature()` formart and the choosed vector propertie ID as the `id_field`.
  
  Parameters:
  - `geometry`: An ee.Feature() object representing the area of interest.
  - `bestEffort`: A boolean indicating whether to use a larger pixel (10m to 30m) if the polygon area is too big (default is False).
  
  Returns:
  - NDVI time series data along with other information for the specified geometry.

### 2.`build_time_series`

  Builds and writes NDVI time series data for a target vector asset, processing one polygon at a time.

  Parameters:
  - `index`: Index of the object being processed.
  - `obj`: Object ID for which the time series is being generated.
  - `id_field`: Field name representing the ID in the vector asset.
  - `outfile`: Output file path to write the time series data.
  - `asset`: Earth Engine vector asset.
  - `bestEffort`: A boolean indicating whether to use a larger scale if needed (default is False).
  
  Returns:
  - True if processing is successful, None if the polygon area is too small, False if an error occurs during processing and restart the process using the bestEffort approach.

### 3.`build_time_series_check`

  Checks the consistency of the NDVI time series library and handles errors during processing.

  Parameters:
  - `index`: Index of the object being processed.
  - `obj`: Object ID for which the time series is being checked.
  - `id_field`: Field name representing the ID in the vector asset.
  - `outfile`: Output file path where time series data is stored.
  - `asset`: Earth Engine vector asset.
  - `checker`: A boolean indicating whether to check if the polygon has been processed before (default is False).
  
  Returns:
  - A dictionary containing information about errors and processing time.

### 4.`build_id_list`

  Builds and writes a text file containing each Polygon ID used to extract the time series.
  
  Parameters:
  - `asset`: Earth Engine vector asset.
  - `id_field`: Field name representing the ID in the vector asset.
  - `colab_folder`: Path of the folder where the text file will be saved.

### 5.`run`

  Manages the overall workflow by catching argument information and initiating the process of extracting NDVI time series data for specified polygonal areas.
  
  Parameters:
  - `asset`: Earth Engine vector asset.
  - `id_field`: Field name representing the ID in the vector asset.
  - `output_name`: Name of the output file.
  - `colab_folder`: Path of the folder where the output file will be saved.
