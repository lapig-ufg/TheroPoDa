#TheroPoDa is HUNGRY, she gonna "eat" all the data of EE and store it in her .db "belly" (SQLite file recognized by the .db extension)"
from theropoda import run as theropoda_run
from theropoda import build_id_list
from trend_analysis import run as trend_run
import os
import argparse
import shutil
import sqlite3
import pandas as pd
from skmap.misc import date_range, ttprint
from skmap import parallel

def run_analysis(asset, id_field, collection, output_name, output_folder, start_date, end_date, window=15,n_cores=12):

  """Main analysis function that can be called directly"""
  # Your existing analysis code here
  print(f"Starting analysis with parameters:")
  print(f"Asset: {asset}")
  print(f"ID Field: {id_field}")
  print(f"Collection: {collection}")
  print(f"Output file: {output_name}")
  print(f"Output folder: {output_folder}")
  print(f"Date Range: {start_date} to {end_date}")
  print(f"Window Size: {window}") 
  print(f"Number of threads: {n_cores}") 
  
  try:
	
    db = asset.split('/')[-1]
    
    colab_folder = output_folder
    
    output_path = os.path.join(output_folder, output_name)

    #conn = sqlite3.connect(output_name+'.db')
    conn = sqlite3.connect(output_path + '.db')
    conn.close()

    #Check if polygon list file exists
    if os.path.isfile(output_path + '_polygonList.txt') is False:
      build_id_list(asset,id_field,colab_folder,output_name)

    theropoda_run(asset,id_field,output_name,colab_folder,db,collection,n_cores=n_cores)

    start_date_trend, end_date_trend= start_date, end_date
    output_file_trends = f'{output_path}_trend_analysis.pq'

    ################################
    ## SQLITE access
    ################################
    ttprint(f"Preparing {output_name}")
    #con = sqlite3.connect(output_name+'.db')
    con = sqlite3.connect(output_path + '.db')
    cur = con.cursor()
    res = cur.execute(f"CREATE INDEX IF NOT EXISTS restoration_id_pol ON restoration ({id_field})")
    con.commit()
    
    ################################
    ## Common data structures
    ################################
    ttprint(f"Preparing polygon ids")
    
    idx_sql = f"SELECT {id_field}, MIN(date) min_date, MAX(date) max_date, COUNT(*) count FROM restoration GROUP BY 1 ORDER BY 1"
    idx =  pd.read_sql_query(idx_sql, con=con)
    
    try:
      window = int(window)
    except:
      if collection == 'Sentinel':
        window = 15 #days
      elif collection == 'Landsat':
        window = 16 #days
      else:
        window = 15 #days

    dt_days = list(date_range(start_date_trend, end_date_trend, date_unit='days', date_step=window, ignore_29feb=True))
    season_size = int(len(dt_days) / window)

    #args = [ (output_name+'.db', r[f'{id_field}'], dt_days, season_size, id_field, output_file_trends) for _, r in idx.iterrows() ]
    args = [ (output_path+ '.db', r[f'{id_field}'], dt_days, season_size, id_field, output_file_trends) for _, r in idx.iterrows() ]
    
    ttprint(f"Starting trend analysis on {len(args)} polygons")
    for id_pol in parallel.job(trend_run, args, joblib_args={'backend': 'multiprocessing'}):
      continue
    
    df2conv = pd.read_parquet(output_file_trends)
    df2conv.to_parquet(f'{output_path}_trend_analysis.parquet')

    shutil.rmtree(output_file_trends)  
    ttprint("Analysis completed successfully!")
    return True
  
  except Exception as e:
    print(f"Analysis failed: {str(e)}")
    return False
  
# Remove or modify the existing if __name__ == '__main__' block
if __name__ == '__main__':
    # Can keep this for command-line usage or remove it
    import argparse
    parser = argparse.ArgumentParser()
    # ... add your argument definitions ...
    args = parser.parse_args()
    run_analysis(**vars(args))
