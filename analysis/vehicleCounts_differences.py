import glob
import pandas as pd
import numpy as np
import os
import csv
import sys
import argparse
from pathlib import Path
import gzip
import geopandas as gdp



def read_txt_as_csv(path):

	print('# Importing file ' + str(path))
	
	unzipped_path = gzip.open(path, 'rb')

	df = pd.read_csv(unzipped_path, delimiter = '\t')

	print('# File imported')

	return df
	
	
	
def clean_linkstats(df, scenario_name):

	# Define LINK column as string values
	df['LINK'] = df['LINK'].astype(str)
	
	# Keep only relevant columns
	df = df[['LINK', 'HRS0-1avg', 'HRS1-2avg', 'HRS2-3avg', 'HRS3-4avg', 'HRS4-5avg', 'HRS5-6avg', 'HRS6-7avg', 'HRS7-8avg', 'HRS8-9avg' ,'HRS9-10avg' ,'HRS10-11avg' ,'HRS11-12avg' ,'HRS12-13avg' ,'HRS13-14avg' ,'HRS14-15avg', 'HRS15-16avg', 'HRS16-17avg', 'HRS17-18avg', 'HRS18-19avg', 'HRS19-20avg', 'HRS20-21avg', 'HRS21-22avg', 'HRS22-23avg','HRS23-24avg', 'HRS0-24avg']]
	
	# Remove strings 'HRS' and 'avg' form each column name
	df.columns = df.columns.str.replace(r'HRS', '')
	df.columns = df.columns.str.replace(r'avg', '')
	
	# Add a prefix to the columns, depending if the file belongs to a scenario or baseline
	if (scenario_name.startswith("S")):
		
		prefix = scenario_name.split('_')[0] + '_'
		df = df.add_prefix(prefix)
		
	else:
		prefix = 'B_'
		df = df.add_prefix(prefix)
	
	# Rename FIRST column name to 'LINK'  (in the previous step it was changed to SX_LINK or B_LINK)	
	df.rename(columns={ df.columns[0]: "LINK" }, inplace = True)
	
	
	return df
		
	
	
def calculate_diff_vehicleCounts(df_B, df_S, scenario_name):
	
	# Merge both dataframes 'many-to-many'
	df = pd.merge(df_B, df_S, on='LINK', validate = 'one_to_one', how = 'outer')
	
	prefix = scenario_name.split('_')[0] + '_'
	
	# Calculate the difference of vehicle counts every hour
	for i in range (25):

		if (i+1 <= 24):
			df['diff_' + str(i) + '-' + str(i+1)] = df[prefix + str(i) + '-' + str(i+1)] - df['B_' + str(i) + '-' + str(i+1)]
	
	# Calculate the total daily vehicle counts difference
	df['diff_0-24'] = df[prefix +'0-24'] - df['B_0-24']
	
	
	return df


def import_shp(path):
	
	gdf = gdp.read_file(path)
	
	return gdf
	
	
def spatial_joint(gp, df):
	
	gd_combined = gp.merge(df, left_on='ID', right_on='LINK', how='left')
	
	return gd_combined
	
	

def export_gpkg(gdf, output_dir, scenario_name):
	
	file_name = scenario_name + '_vehicleCounts_diff.gpkg'
		
	filepath = os.path.join(output_dir, file_name)
	
	print('# Exporting vehicle counts in baseline, ' + scenario_name + ' and their differences as geopackage to: ', filepath)
	
	gdf.to_file(filepath, driver="GPKG", engine="pyogrio")





def main (scenario_name: str, scenario_linkstats_filepath: str, baseline_linkstats_filepath: str, links_shp_filepath: str, output_dir_path : str):
	
	# Convert str filepahts into real filepaths
	scenario_linkstats = Path(scenario_linkstats_filepath)
	baseline_linkstats = Path(baseline_linkstats_filepath)
	links_shp = Path(links_shp_filepath)
	output_dir = Path(output_dir_path)
	
	
	# Check if input files exist:
	print('\n* Checking if input files exist:')
	Input_filePaths_list = [scenario_linkstats, baseline_linkstats, links_shp]
	
	for inputPath in Input_filePaths_list:
		if inputPath.exists():
			print('File ' + str(inputPath) + ' found.')
		else:
			print('\n*** File ' + str(inputPath) + ' was not found!. Check if the given path is correct and exists.\n')
			sys.exit()
	
	
	# Check if output directories exist:
	print('\n* Checking if output directories exist:')
	directory_filePaths_list = [output_dir]
	
	for directoryPath in directory_filePaths_list:
		if directoryPath.exists():
			print('Directory ' + str(directoryPath) + ' found.')
		else:
			print('\n*** Directory ' + str(directoryPath) + ' was not found!. Check if the given directory is correct and exists.\n')
			sys.exit()
	
	print('\n----> Input files and output directories succesfully identified!\n')
	
	
	# Read linkstats files
	df_scenario_linkstats = read_txt_as_csv(scenario_linkstats)
	df_baseline_linkstats = read_txt_as_csv(baseline_linkstats)
	
	# Clean linkstats
	df_scenario_linkstats_clean = clean_linkstats(df_scenario_linkstats, scenario_name)
	df_baseline_linkstats_clean = clean_linkstats(df_baseline_linkstats, 'random_value_different_to_scenarioName')
	
	# Combine linktstats and calculate their vehicle counts differences
	df_linkstats_comparison = calculate_diff_vehicleCounts(df_baseline_linkstats_clean, df_scenario_linkstats_clean, scenario_name)
	
	# Import transport network 
	gp_links = import_shp(links_shp)
	
	# Merge transport network with the vehicle counts
	gp_links_vehCounts_comp = spatial_joint(gp_links, df_linkstats_comparison)
	
	# Export transport network with the vehicle counts as geopackage 
	export_gpkg(gp_links_vehCounts_comp, output_dir, scenario_name)
	
	print('\nProcess has finished. Check the results, amigo!\n\n')
	



if __name__ == "__main__":
	
	p = argparse.ArgumentParser()

	p.add_argument(
		'--scenario_name',
		required=True,
		type=str,
		help="Name of the scenario to be compared (e.g. S1_A1, S3_RedheughBridge, etc.). It must start with 'S'"
	)
	
	p.add_argument(
		'--scenario_linkstats_filepath',
		required=True,
		type=str,
		help="Compressed *.linkstats.txt file from the scenario"
	)
	
	p.add_argument(
		'--baseline_linkstats_filepath',
		required=True,
		type=str,
		help="Compressed *.linkstats.txt file from the baseline"
	)
	
	p.add_argument(
		'--links_shp_filepath',
		required=True,
		type=str,
		help="Transport network in shp format"
	)
	
	p.add_argument(
		'--output_dir_path',
		required=True,
		type=str,
		help="Output directory"
	)
	
	args = p.parse_args()


	main(
		scenario_name = args.scenario_name,
		scenario_linkstats_filepath = args.scenario_linkstats_filepath,
		baseline_linkstats_filepath = args.baseline_linkstats_filepath,
		links_shp_filepath = args.links_shp_filepath,
		output_dir_path = args.output_dir_path
	)