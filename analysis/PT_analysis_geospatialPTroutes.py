import pandas as pd
import numpy as np
import os
import csv
import argparse
from pathlib import Path
import gzip
import xml.etree.ElementTree as ET
import sys
import geopandas as gdp
import geodatasets

# unreferenced but used by other packages
import pyogrio  # for faster exporting


###########################################################################################################

# Python code to extract PT information from MATSim events files, for both BASELINE and a SCENARIO:


## CSV file containing information about when (time in seconds) each PT vehicle enters a link in the baseline
#### --> Column names: vehicle_id, link_id, time_id

## CSV file containing information about when (time in seconds) each PT vehicle enters a link in the scenario
#### --> Column names: vehicle_id, link_id, time_id
## CSV file comparing PT vehicles services (departure, arrival, trip and difference times) between baseline and the scenario simulated
#### --> Column names: vehicle_id, transitLine_id, transitRoute_id, B_depTime, B_arrTime, B_tripTime, S_depTime, S_arrTime, S_tripTime, ServiceTime_DIFF

## CSV file comparing PT vehicles services (departure, arrival, trip and difference times) between baseline and the scenario simulated  BUT ALSO including when agents LEAVE the PT vehicle. This is to quantify potential delays for each passenger when compared to the baseline
#### --> Column names: (vehicle_id	transitLine_id	transitRoute_id	B_depTime	person_id	B_arrTime	B_tripTime	S_depTime	S_arrTime	S_tripTime	ServiceTime_DIFF)

## Geopackage file with PT vehicles' routes in the baseline
## Geopackage file with PT vehicles' routes in the scenario


###########################################################################################################

def read_txt_as_csv(path):

	print('# Importing file ' + str(path))
	
	df = pd.read_csv(path, delimiter = '\t', header=None)
	df.columns = ['PT_id']
	
	print('# File imported')

	return df


def ptServices_details(events_file, df_ptVehicles):

	# read events file
	print('# Decompressing zip file ' + str(events_file))
	xml_input = gzip.open(events_file, 'rb')
	
	print('# Opening file...')
	tree = ET.parse(xml_input)
	root = tree.getroot()

	# create empty lists to store data later (departure and arrival info)
	pt_departure_list = []
	pt_arrival_passengers_list = []
	pt_arrival_list = []
	pt_routeLink_time_list = []
	
	# Create a list of unique pt vehicles' ID
	ptVehicles_list = df_ptVehicles['PT_id'].unique().tolist()

	print('# Reading and identifying public transport services...')
	for child in root:
		
		type_event = (child.attrib['type'])
		
		if (type_event == 'TransitDriverStarts'):
			
			temp_departure_list = []
			
			depVehicle_id = (child.attrib['vehicleId'])
			transitLine_id = (child.attrib["transitLineId"])
			transitRoute_id = (child.attrib["transitRouteId"])
			depTime = float(child.attrib["time"])
			
			temp_departure_list.append(depVehicle_id)
			temp_departure_list.append(transitLine_id)
			temp_departure_list.append(transitRoute_id)
			temp_departure_list.append(depTime)
			
			pt_departure_list.append(temp_departure_list)
		
		# check if the events belong to a person leaving the vehicle. 
		elif ((type_event == 'PersonLeavesVehicle')):
			
			temp_arrival_passenger_list = []
			
			arrVehicle_id = (child.attrib['vehicle'])
			person_id = (child.attrib['person'])
			arrTime = float(child.attrib["time"])
			
			temp_arrival_passenger_list.append(arrVehicle_id)
			temp_arrival_passenger_list.append(person_id)
			temp_arrival_passenger_list.append(arrTime)
			
			pt_arrival_passengers_list.append(temp_arrival_passenger_list)
		
			# check if the events belong to a person driving the vehicle only (person='pt_**'). 
			if ('pt_' in (child.attrib['person'])):
			
				temp_arrival_list = []
			
				arrVehicle_id = (child.attrib['vehicle'])
				arrTime = float(child.attrib["time"])
			
				temp_arrival_list.append(arrVehicle_id)
				temp_arrival_list.append(arrTime)
			
				pt_arrival_list.append(temp_arrival_list)
			
		
		# Get all links used by the pt vehicles
		elif (((type_event == 'entered link') or (type_event == 'vehicle enters traffic')) and (child.attrib['vehicle'] in ptVehicles_list)):

			temp_list = []
			
			vehicle_id = (child.attrib['vehicle'])
			link_id = (child.attrib["link"])
			time_id = (child.attrib["time"])

			temp_list.append(vehicle_id)
			temp_list.append(link_id)
			temp_list.append(time_id)
				
			pt_routeLink_time_list.append(temp_list) 
		
	
	print('# Public transport services identified')
	
	# Create datafranes
	df_ptDeparture = pd.DataFrame(pt_departure_list)
	df_ptDeparture.columns =['vehicle_id','transitLine_id', 'transitRoute_id', 'depTime']
	
	df_ptArrival_passengers = pd.DataFrame(pt_arrival_passengers_list)
	df_ptArrival_passengers.columns =['vehicle_id', 'person_id', 'arrTime']
	
	df_ptArrival = pd.DataFrame(pt_arrival_list)
	df_ptArrival.columns =['vehicle_id', 'arrTime']
	
	df_pt_routeLink_time = pd.DataFrame(pt_routeLink_time_list)
	df_pt_routeLink_time.columns =['vehicle_id','link_id', 'time_id']
	
	# Merge dataframes based on vehicle_id column
	## Merge to get only information about pt departure and arrival time
	df_ptServicesTime = df_ptDeparture.merge(df_ptArrival, on=['vehicle_id'], how='left')
	df_ptServicesTime['tripTime'] = df_ptServicesTime['arrTime'] - df_ptServicesTime['depTime']
	
	## Merge to get both information about pt departure and arrival time and when passengers leave the pt vehicle
	df_ptServicesPassengers_Time = df_ptDeparture.merge(df_ptArrival_passengers, on=['vehicle_id'], how='left')
	df_ptServicesPassengers_Time['tripTime'] = df_ptServicesPassengers_Time['arrTime'] - df_ptServicesPassengers_Time['depTime']
	
	return df_ptServicesTime, df_ptServicesPassengers_Time, df_pt_routeLink_time


def clean_and_merge_df(db_b, db_s):
	
	# rename some of the columns:
	db_b.rename(columns={'depTime': 'B_depTime', 'arrTime': 'B_arrTime', 'tripTime': 'B_tripTime'}, inplace=True)
	db_s.rename(columns={'depTime': 'S_depTime', 'arrTime': 'S_arrTime', 'tripTime': 'S_tripTime'}, inplace=True)
	
	columns_list = list(db_b.columns.values)
	
	if ('person_id' in columns_list):
		# Combine both dataframes
		df = db_b.merge(db_s, on=['vehicle_id', 'transitLine_id', 'transitRoute_id', 'person_id'], how='outer')
	else:
		# Combine both dataframes
		df = db_b.merge(db_s, on=['vehicle_id', 'transitLine_id', 'transitRoute_id'], how='outer')
		
	# Calculate the trip difference for each pt service route
	df['ServiceTime_DIFF'] = df['S_tripTime'] -  df['B_tripTime']
	
	return df


def import_shp(path):
	
	gdf = gdp.read_file(path)
	
	return gdf
	
	
def merge_and_dissolve_geom(gdf_network, df_routes, df_vehiclesInfo):
	
	# Merge routes and vehicles' info ('transitLine_id' and 'transitRoute_id')
	df_routes_info = df_routes.merge(df_vehiclesInfo[['vehicle_id', 'transitLine_id', 'transitRoute_id']], on ='vehicle_id', how='left')
	
	# keep only relevant columns
	df_routes_info_clean = df_routes_info[['vehicle_id', 'transitLine_id', 'transitRoute_id', 'link_id']]
	
	# Merge transport network
	gd_combined = gdf_network[['ID', 'geometry']].merge(df_routes_info_clean, left_on='ID', right_on='link_id', how='right')
	
	# Dissolve geometry based on vehicle_id attribute
	gp_dissolved = gd_combined.dissolve(by='vehicle_id')
	
	# Create a new column with 'vehicle_id' values, as they were converted into index column.
	gp_dissolved['vehicle_id'] = gp_dissolved.index
	
	# Reset index
	gp_dissolved.reset_index(drop=True, inplace=True)
	
	# Keep only relevant columns:
	gp_dissolved = gp_dissolved[['vehicle_id', 'transitLine_id', 'transitRoute_id', 'geometry']]
	
	return gp_dissolved


def export_df_to_csv(df, output_dir, scenario_name, name_type):
	
	suffix = '.csv'
	file_name = 'df_' + name_type + scenario_name
	filepath = os.path.join(output_dir, file_name + suffix)
	
	print('# Exporting file to: ', filepath)

	df.to_csv(filepath, index=False, sep=';')

	print('# Exported succesfully')
	

def export_as_gpkg(gdf, output_dir, scenario_name, name_type):
	
	suffix = '.gpkg'
	file_name = scenario_name + '_' + name_type + suffix
	filepath = os.path.join(output_dir, file_name)
	
	print('# Exporting public transport vehicles routes as geopackage to: ', filepath)
	
	gdf.to_file(filepath, driver="GPKG", engine="pyogrio")
	
	print('# Exported succesfully')


def main(baseline_events_filepath: str, scenario_events_filepath:str, scenario_name:str, pt_vehicles_filepath: str, links_shp_filepath: str, output_dir_filepath: str):
	
	baseline_events = Path(baseline_events_filepath)
	scenario_events = Path(scenario_events_filepath)
	pt_vehicles = Path(pt_vehicles_filepath)
	links_shp = Path(links_shp_filepath)
	output_dir = Path(output_dir_filepath)
	
	
	# Check if input files exist:
	print('\n* Checking if input files exist:')
	Input_filePaths_list = [baseline_events, scenario_events, pt_vehicles, links_shp]
	
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
	
	
	# Read the pt vehicles file and create a dataframe
	df_ptVehicles = read_txt_as_csv(pt_vehicles)
	
	# Read the events files, extract the required information and create dataframes containg the extract data
	df_baseline_ptServicesTime, df_baseline_ptServicesPassengers_Time, df_baseline_pt_routeLink_time = ptServices_details(baseline_events, df_ptVehicles)
	df_scenario_ptServicesTime, df_scenario_ptServicesPassengers_Time, df_scenario_pt_routeLink_time = ptServices_details(scenario_events, df_ptVehicles)
	
	# Clean and merge previous dataframes
	df_ptServices = clean_and_merge_df(df_baseline_ptServicesTime, df_scenario_ptServicesTime)
	df_ptServices_Passengers = clean_and_merge_df(df_baseline_ptServicesPassengers_Time, df_scenario_ptServicesPassengers_Time)
	
	# Import transport network 
	gp_links = import_shp(links_shp)
	
	# Merge transport network with the vehicle counts and dissolve geometry based on 'vehicle_id' attribute.
	#gp_ptVehicleRoutes_baseline = merge_and_dissolve_geom(gp_links, df_baseline_pt_routeLink_time, df_baseline_ptServicesTime)   --> uncomment this line and line #276 if baseline pt routes want to be exported
	gp_ptVehicleRoutes_scenario = merge_and_dissolve_geom(gp_links, df_scenario_pt_routeLink_time, df_scenario_ptServicesTime)
	
	# Export geodataframes as geopackages
	#export_as_gpkg(gp_ptVehicleRoutes_baseline, output_dir, scenario_name, 'Baseline_ptVehiclesRoutes') --> uncomment this line and line #272 if baseline pt routes want to be exported
	export_as_gpkg(gp_ptVehicleRoutes_scenario, output_dir, scenario_name, 'Scenario_ptVehiclesRoutes')
	
	# Export dataframes as csv files
	export_df_to_csv(df_ptServices, output_dir, scenario_name, 'ptServices_baseline_vs_')
	export_df_to_csv(df_ptServices_Passengers, output_dir, scenario_name, 'ptServicesAndPassengersEgress_baseline_vs_')
	export_df_to_csv(df_baseline_pt_routeLink_time, output_dir, scenario_name, 'allBaselinePtRoutes_')
	export_df_to_csv(df_scenario_pt_routeLink_time, output_dir, scenario_name, 'allScenarioPtRoutes_')
	
	print('# The programm has finished. Check the results, amigo!\n\n')
	

if __name__ == "__main__":
	p = argparse.ArgumentParser()

	p.add_argument(
		'--baseline_events_filepath',
		required=True,
		type=str,
		help="Compressed Baseline events.xml.gz"
	)
		
	p.add_argument(
		'--scenario_events_filepath',
		required=True,
		type=str,
		help="Compressed Scenario events.xml.gz"
	)
	
	p.add_argument(
		'--scenario_name',
		required=True,
		type=str,
		help="Name given to the scenario"
	)
	
	p.add_argument(
		'--pt_vehicles_filepath',
		required=True,
		type=str,
		help="Txt file containing the name of the different public transport vehicles. Obtained from Simunto Via. Alternatively, they can be obtained after quering MATSim events.xml files"
	)
	
	p.add_argument(
		'--links_shp_filepath',
		required=True,
		type=str,
		help="Transport network in shp format"
	)
	
	p.add_argument(
		'--output_dir_filepath',
		required=True,
		type=str,
		help="Directory to save the generated outputs"
	)
	
	
	args = p.parse_args()


	main(
		baseline_events_filepath=args.baseline_events_filepath,
		scenario_events_filepath=args.scenario_events_filepath,
		scenario_name=args.scenario_name,
		pt_vehicles_filepath=args.pt_vehicles_filepath,
		links_shp_filepath = args.links_shp_filepath,
		output_dir_filepath=args.output_dir_filepath
	)