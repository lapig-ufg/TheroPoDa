# -*- coding: utf-8 -*-
"""TheroPoDa.py

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/github/vieiramesquita/TheroPoDa/blob/main/TheroPoDa.ipynb

### Name
T(h)eroPoDa - Time Series Extraction for Polygonal Data + Trend Analysis

### Description
Toolkit created to extract Time Series information from Sentinel 2 stored in Earth Engine, perform gap filling and trend analysis image

### Author
  Vinícius Vieira Mesquita - vieiramesquita@gmail.com

### Version
  1.1.0

### Import main libraries

### Requirements (installation order from top to bottom)
- Python 3.10
- GDAL
- Rasterio 
- Pandas
- Geopandas
- Scikit-learn
- Joblib
- Psutil
- Earthengine-api - https://developers.google.com/earth-engine/guides/python_install
- scikit-map - https://github.com/openlandmap/scikit-map

Run the following cell to import the main API's into your session.
"""

# Commented out IPython magic to ensure Python compatibility.
# %%capture
# if 'google.colab' in str(get_ipython()):
#   !pip install earthengine-api
#   !pip install pandas
#   !pip instal joblib

import os
import time
import ee
import pandas as pd
from joblib import Parallel, delayed
from loguru import logger
import sqlite3
from skmap.misc import date_range, ttprint
from trend_analysis import run as trend_run
from skmap import parallel
import argparse
import pyarrow as pa
import pyarrow.parquet as pq


logger.add("log_do_.log", rotation="500 MB")

"""### Authenticate and initialize

Run the `ee.Authenticate` function to authenticate your access to Earth Engine servers and `ee.Initialize` to initialize it. Upon running the following cell you'll be asked to grant Earth Engine access to your Google account. Follow the instructions printed to the cell.
"""

# Trigger the authentication flow.
#ee.Authenticate()

# Initialize the library.
ee.Initialize(opt_url='https://earthengine-highvolume.googleapis.com')

"""### Get the NDVI Time Series from Earth Engine

Function responsible to get the time series of Sentinel 2 data throught Earth Engine.

This function needs a `geometry` object in the `ee.Feature()` formart and the choosed vetor propertie ID as the `id_field`.


"""
#Returns a NDVI time series (and other informations) by a target polygon
def getTimeSeries(geometry,bestEffort=False):
  
  """
  Retrieves NDVI time series data from Sentinel 2 imagery for a specified geometry.

  Parameters:
  - geometry: An ee.Feature() object representing the area of interest.
  - bestEffort: A boolean indicating whether to use a larger pixel (10m to 30m) if the polygon area is too big (default is False).

  Returns:
  - NDVI time series data along with other information for the specified geometry.
  """
  
  #Mask possible edges which can occur on Sentinel 2 data
  def maskEdges(img):
    """
    Masks possible edges that may occur in Sentinel 2 data.

    Parameters:
    - img: Input image.

    Returns:
    - Masked image.
    """
    return img.updateMask(img.select('B8A').mask().updateMask(img.select('B9').mask()));

  #Creates a Cloud and Shadow mask for the input Sentinel 2 image
  def mask_and_ndvi(img):
    """
    Creates a cloud and shadow mask for the input Sentinel 2 image and calculates NDVI.

    Parameters:
    - img: Input image.

    Returns:
    - Image with cloud and shadow mask and NDVI calculated.
    """

    #Get spacecraft plataform name
    satName = ee.String(img.get('SPACECRAFT_NAME'))

    #Remove cloud and shadow from images
    mask = img.select('cs').gte(0.5)
    
    bad_values_filter = img.select('B8').gte(0)

    #Calculate NDVI (Normalized Difference Vegetation Index) based on Bands 4 (Red) and 8 (Near Infrared)
    ndvi = img.updateMask(mask.multiply(bad_values_filter)).normalizedDifference(['B8','B4']).select([0],['NDVI'])

    return (img.addBands([ndvi,ee.Image.constant(1).rename(['full'])], None, True)
      .set({'system:time_start':img.get('system:time_start'),'satelite':satName}))

  #Extracts and standardizes the output NDVI values and etc. by each image
  def reduceData(img):
    """
    Extracts and standardizes NDVI values and other information from each image.

    Parameters:
    - img: Input image.

    Returns:
    - Standardized information extracted from the image.
    """

    img = ee.Image(img)

    #Get the date which the image was taken
    imgDate = ee.Date(ee.Number(img.get('system:time_start')))

    #Organize the time for the outuput NDVI information
    orgDate = (ee.String(ee.Number(imgDate.get('year')).toInt().format())
      .cat('-')
      .cat(ee.String(ee.Number(imgDate.get('month')).toInt().format()))
      .cat('-')
      .cat(ee.String(ee.Number(imgDate.get('day')).toInt().format()))
      )

    #Defines the zonal reducers to use
    reducers = (ee.Reducer.mean()
        .combine(**{'reducer2': ee.Reducer.stdDev(),'sharedInputs':True,})
        .combine(**{'reducer2': ee.Reducer.median(),'sharedInputs':True,})
        .combine(**{'reducer2': ee.Reducer.min(),'sharedInputs':True,})
        .combine(**{'reducer2': ee.Reducer.max(),'sharedInputs':True,})
        .combine(**{'reducer2': ee.Reducer.count(),'sharedInputs':True}))

    pixel_size = 10

    #If polygon area is to big and causes memory limit error, bestEffort is used
    #bestEffort - If the polygon would contain too many pixels at the given scale, compute and use a larger scale which would allow the operation to succeed.

    if bestEffort == False:
      series = img.reduceRegion(reducers,ee.Feature(geometry).geometry(), pixel_size,None,None,False,1e13,16)

    else:
      pixel_size = 30
      series = img.reduceRegion(reducers,ee.Feature(geometry).geometry(), pixel_size,None,None,False,1e13,16)

    #Return defined information for the choosed polygon
    return (ee.Feature(geometry)
      .set('id',ee.String(img.id())) #Image ID
      .set('date',orgDate) #Date
      .set('satelite',img.get('satelite')) #Sapacraft plataform name (i.e. Sentinel 2A or 2B)
      .set('MGRS_TILE',img.get('MGRS_TILE')) #Reference tile grid
      .set('AREA_HA',ee.Feature(geometry).area(1).divide(10000)) #Choosed polygon ID Field
      #.set('NDVI_mean',ee.Number(ee.Dictionary(series).get('NDVI_mean'))) #NDVI pixel average for the polygon
      .set('NDVI_median',ee.Number(ee.Dictionary(series).get('NDVI_median'))) #NDVI pixel median for the polygon
      #.set('NDVI_min',ee.Number(ee.Dictionary(series).get('NDVI_min'))) #NDVI pixel minimum value for the polygon
      #.set('NDVI_max',ee.Number(ee.Dictionary(series).get('NDVI_max'))) #NDVI pixel maximum value for the polygon
      #.set('NDVI_stdDev',ee.Number(ee.Dictionary(series).get('NDVI_stdDev'))) #NDVI pixel Standard Deviation for the polygon
      .set('Pixel_Count',ee.Number(ee.Dictionary(series).get('NDVI_count'))) #Number of pixels cloudless and shadowless used for estimatives
      .set('Total_Pixels',ee.Number(ee.Dictionary(series).get('full_count'))) #Total number of pixels inside the polygon
      .set('Pixel_Size',pixel_size) #Size of the pixel used
    )

  #Turns Feature into Dictionary to get properties
  def toDict(feat):
    """
    Converts a Feature into a Dictionary to get properties.

    Parameters:
    - feat: Input Feature.

    Returns:
    - Dictionary representation of the Feature.
    """
    return ee.Feature(feat).toDictionary()

  #Calls the Sentinel 2 data collection, filter the images based in the polygon location, masks cloud/shadow and calculates NDVI
  s2 = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(geometry.geometry()))

  csPlus = (ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED')
				.filterBounds(geometry.geometry()))

  csPlusBands = csPlus.first().bandNames();

  imgCol = (s2.linkCollection(csPlus, csPlusBands)
        .map(maskEdges)
        .map(mask_and_ndvi))

  #Extracts NDVI time series by polygon, remove the nulls and build a dictionary struture to the data
  Coll_fill = (imgCol.toList(imgCol.size()).map(reduceData)
    .filter(ee.Filter.notNull(['NDVI_mean']))
    .map(toDict)
    )

  return Coll_fill

"""### Build and Structure the Time Series library

Function responsible to build and structure the time series library.
"""

#Builds and writes a NDVI time series with Sentinel 2 data by a target vector asset
def build_time_series(index,obj,id_field,outfile,asset,bestEffort=False):
  
  """
  Builds and writes NDVI time series data for a target vector asset, processing one polygon at a time.

  Parameters:
  - index: Index of the object being processed.
  - obj: Object ID for which the time series is being generated.
  - id_field: Field name representing the ID in the vector asset.
  - outfile: Output file path to write the time series data.
  - asset: Earth Engine vector asset.
  - bestEffort: A boolean indicating whether to use a larger scale if needed (default is False).

  Returns:
  - True if processing is successful, None if the polygon area is too small, False if an error occurs during processing.
  """

  #Main polygon asset
  samples = ee.FeatureCollection(asset).select(id_field)

  #Creates an empty data.frame for the time series
  df = pd.DataFrame()

  #Processing time start variable
  start_time_obj = time.time()

  #Selects the target polygon
  selected_sample = samples.filter(ee.Filter.eq(id_field,obj)).first()

  #Extracts the formated NDVI time series from the target polygon
  point_series = getTimeSeries(ee.Feature(selected_sample),bestEffort).getInfo()

  #Writes the time series by data frame row
  for item in point_series:
    df  = pd.concat([df,pd.DataFrame(item,index=[0])])

  #Rounds the NDVI values by four decimals (avoid huge and slow tables)
  df['AREA_HA'] = df['AREA_HA'].round(decimals=4)
  df['NDVI_mean'] = df['NDVI_mean'].round(decimals=4)
  df['NDVI_stdDev'] = df['NDVI_stdDev'].round(decimals=4)
  df['NDVI_max'] = df['NDVI_max'].round(decimals=4)
  df['NDVI_min'] = df['NDVI_min'].round(decimals=4)
  df['NDVI_median'] = df['NDVI_median'].round(decimals=4)
  df['date'] = pd.to_datetime(df['date'])

  conn = sqlite3.connect(outfile)

  df.to_sql('restoration',conn,if_exists='append',index = False)

  conn.close()

  #Estimates the total time spent in the generation of the time series for the target polygon
  time_spent = round(time.time() - start_time_obj, 3)

  logger.success(f'Index {index} - Object [{obj}] procesed in {round(time.time() - start_time_obj, 3)} seconds')

  #Returns checkers
  if df.shape[0] > 0:
    return True,time_spent #if everthings works fine, returns the True and the time spend
  elif float(df['AREA_HA']) < 0.01:
    return None,None #If the polygon area is too small, ignores the polygon!
  else:
    return False,None #if something goes wrong, returns False

"""### Check the Time Series library

Function responsible to check the consistency of the time series library.
"""

#Checks if time series processing works
def build_time_series_check(index,obj,id_field,outfile,asset,checker=False):
  
  """
  Checks the consistency of the NDVI time series library and handles errors during processing.

  Parameters:
  - index: Index of the object being processed.
  - obj: Object ID for which the time series is being checked.
  - id_field: Field name representing the ID in the vector asset.
  - outfile: Output file path where time series data is stored.
  - asset: Earth Engine vector asset.
  - checker: A boolean indicating whether to check if the polygon has been processed before (default is False).

  Returns:
  - Dictionary containing information about errors and processing time.
  """

  obj = int(obj)

  #Checks if the polygon was been processed before
  if checker is True:

    conn = sqlite3.connect(outfile)

    #df_check = pd.read_sql(outfile)
    try:
      df_check_list = pd.read_sql_query("SELECT DISTINCT ID_POL FROM restoration", conn)
      df_check_list = list(df_check_list['ID_POL'])
    except:
      df_check_list = []

    conn.close()

    if obj in df_check_list:

      logger.info(f' Object [{obj}] was found in the file. Skipping..')
      return {'errors':None, 'time': 0}


  #
  errors = None
  #
  time = None


  try:
    check = build_time_series(index,obj,id_field,outfile,asset)
    time = check[1]

    if check[0] == False:
      logger.debug('raised')
      raise
    if check[0] == None:
      return {'errors':'ignore' ,'time': 'ignore'}

  except:

    try:

      logger.exception(f'Index {index} - Request [{obj}] fails. Trying the best effort!')

      check = build_time_series(index,obj,id_field,outfile,asset,True)

      if check[0] == False:
        logger.debug('raised')
        raise

      if check[0] == None:
        return {'errors':'ignore' ,'time': 'ignore'}

    except:

      logger.error(f'Index {index} - Request [{obj}] expired. Sending it to the error list!')

      errors = obj

  return {'errors':errors ,'time': time}

"""### Build the Polygon List file

Function responsible to write a text file contaning each Polygon ID used to extract the time series.
"""

#Builds and writes the Polygon ID list
def build_id_list(asset,id_field,colab_folder):
  """
  Builds and writes a text file containing each Polygon ID used to extract the time series.

  Parameters:
  - asset: Earth Engine vector asset.
  - id_field: Field name representing the ID in the vector asset.
  - colab_folder: Path of the folder where the text file will be saved.
  """

  #Loads EE Polygon asset
  samples = ee.FeatureCollection(asset).select(id_field)

  #Estimates the number of polygons in the Asset
  sample_size = int(samples.size().getInfo())

  #Conditionals to avoid Earth Engine memory erros
  #Earth Engine is limited to request 50k vectors, make manual lists if you need more!
  if sample_size < 50000:
    samples_list = samples.toList(50000)
  else:
    samples_list = samples.toList(samples.size())

  fileName = os.path.join(colab_folder,db + '_polygonList.txt')

  with open(fileName, "w") as polygon_file:

    def get_ids(feat):
      return ee.Feature(feat).get(id_field)

    samples_list_slice = samples_list.map(get_ids).sort().getInfo()

    for polygon in samples_list_slice:
      polygon_file.write(str(polygon)+ '\n')

"""### Run

Function responsible to catch argument information and start run the process.
"""

def run(asset,id_field,output_name,colab_folder):
  """
  Manages the overall workflow by catching argument information and initiating the process of extracting NDVI time series data for specified polygonal areas.

  Parameters:
  - asset: Earth Engine vector asset.
  - id_field: Field name representing the ID in the vector asset.
  - output_name: Name of the output file.
  - colab_folder: Path of the folder where the output file will be saved.
  """

  output_name = os.path.join(colab_folder,output_name)

  start_time = time.time()

  fileName_polyList = os.path.join(colab_folder,db + '_polygonList.txt')

  #Reading the file which contains the polygons IDs
  listPolygons_text = open(fileName_polyList,"r")
  listPolygons_text = listPolygons_text.readlines()

  #Format the data
  listPolygons_text = [int(name) for name in listPolygons_text]

  start_obj = 0

  #Estimates the total of polygons
  total = len(listPolygons_text)

  logger.info(f'Number of objects to process: {total}')

  #Yes, it will take a long time to finish!
  if total > 1000:
    logger.info('Go take a coffee and watch a series... it will take a while!')

  list_num = listPolygons_text[start_obj:total]

  #Checkers
  first_dict = [{'errors':'ignore' ,'time': 'ignore'}]
  check_file = True

  #Structures the arguments for jobLib::Parallel
  worker_args = [
    (listPolygons_text.index(obj),obj,id_field,output_name,asset,check_file) \
    for obj in list_num
  ]

  #Number of to use (more than 20 generate many sleeping queries)
  n_cores = 14 #Recommended

  #Starts the parallel processing
  infos = Parallel(n_jobs=n_cores, backend='multiprocessing')(delayed(build_time_series_check)(*args) for args in worker_args)

  if check_file is True:
    first_dict = {'time': 0}

  #List with all times computed during the processing
  time_list = [first_dict['time']] + [item['time'] for item in infos if item['time'] != None]

  #List of polygons probably with errors
  errors_list = [item['errors'] for item in infos if item['errors'] != None]

  fileName_errors = os.path.join(colab_folder,db + '_errors_polygon.txt')

  #Write a file with the erros list
  with open(fileName_errors, "w") as errors_file:
    for polygon in errors_list:
      errors_file.write(str(polygon)+ '\n')

  logger.success(f'The average processing time was {round(pd.DataFrame(time_list).mean()[0],2)} seconds')
  logger.success(f'Processing finished. All the work took {round(time.time() - start_time,3)} seconds to complete')

#from google.colab import drive
#drive.mount('/content/drive/')

if __name__ == '__main__':

  parser = argparse.ArgumentParser(description='Toolkit created to extract Time Series information from Sentinel 2 stored in Earth Engine, perform gap filling and trend analysis image.')
    
  parser.add_argument('--asset', type=str, required=True, help='The asset name or path')
  parser.add_argument('--id_field', type=str, required=True, help='The ID field name')
  parser.add_argument('--output_name', type=str, required=True, help='The output file name')

  args = parser.parse_args()

  asset = args.asset #'users/vieiramesquita/LAPIG_FieldSamples/lapig_goias_fieldwork_2022_50m' #Earth Engine Vector Asset
  id_field = args.id_field #'ID_POINTS' #Vector collumn used as ID (use unique identifiers!)
	
  db = asset.split('/')[-1]
  
  db_name = db + '.db'  
  
  colab_folder = ''
  output_name = args.output_name #db_name

  conn = sqlite3.connect(db_name)
  conn.close()

  #Check if polygon list file exists
  if os.path.exists(os.path.join(colab_folder,db + '_polygonList.txt')) is False:
    build_id_list(asset,id_field,colab_folder)

  run(asset,id_field,output_name,colab_folder)

  input_file = output_name
  start_date_trend, end_date_trend= '2019-01-01', '2024-01-01'
  output_file_trends = f'{output_name[:-3]}_trend_analysis.pq'

  ################################
  ## SQLITE access
  ################################
  ttprint(f"Preparing {output_name}")
  con = sqlite3.connect(output_name)
  cur = con.cursor()
  res = cur.execute(f"CREATE INDEX IF NOT EXISTS restoration_id_pol ON restoration ({id_field})")
  con.commit()
  
  ################################
  ## Common data structures
  ################################
  ttprint(f"Preparing polygon ids")
  
  idx_sql = f"SELECT {id_field}, MIN(date) min_date, MAX(date) max_date, COUNT(*) count FROM restoration GROUP BY 1 ORDER BY 1"
  idx =  pd.read_sql_query(idx_sql, con=con)
  
  dt_5days = list(date_range(start_date_trend, end_date_trend, date_unit='days', date_step=5, ignore_29feb=True))
  season_size = int(len(dt_5days) / 5)

  args = [ (output_name, r[f'{id_field}'], dt_5days, season_size, id_field, output_file_trends) for _, r in idx.iterrows() ]
  
  ttprint(f"Starting trend analysis on {len(args)} polygons")
  for id_pol in parallel.job(trend_run, args, joblib_args={'backend': 'multiprocessing'}):
    continue
  
  df2conv = pd.read_parquet(output_file_trends)
  df2conv.to_parquet(f'{output_name[:-3]}_trend_analysis.parquet')
  df2conv = None
  shutil.rmtree(df2conv) 
