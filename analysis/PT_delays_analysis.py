import pandas as pd
import numpy as np
import os
import csv
import matsim
import argparse
from pathlib import Path
import gzip
import xml.etree.ElementTree as ET
import sys


def ptServices_details(events_file):

	# read events file
	print('# Decompressing zip file ' + str(events_file))
	xml_input = gzip.open(events_file, 'rb')
	
	print('# Opening file...')
	tree = ET.parse(xml_input)
	root = tree.getroot()

	# create empty lists to store data later (departure and arrival info)
	pt_departure_list = []
	pt_arrival_list = []

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
		
		# check if the events belong to a person leaving the vehicle AND to a pt driver. 
		# If this second part ('pt_') is not considered, each passenger leaving the pt service will create a record
		if ((type_event == 'PersonLeavesVehicle') and ('pt_' in (child.attrib['person']))):
			
			temp_arrival_list = []
			
			arrVehicle_id = (child.attrib['vehicle'])
			arrTime = float(child.attrib["time"])
			
			temp_arrival_list.append(arrVehicle_id)
			temp_arrival_list.append(arrTime)
			
			pt_arrival_list.append(temp_arrival_list)
		
	
	print('# Public transport services identified')
	
	# Create a datafrane
	df_ptDeparture = pd.DataFrame(pt_departure_list)
	df_ptDeparture.columns =['vehicle_id','transitLine_id', 'transitRoute_id', 'depTime']
	
	# Create a datafrane
	df_ptArrival = pd.DataFrame(pt_arrival_list)
	df_ptArrival.columns =['vehicle_id', 'arrTime']
	
	# Merge both dataframes based on vehicle_id column
	df_ptServicesTime = df_ptDeparture.merge(df_ptArrival, on=['vehicle_id'], how='left')
	
	df_ptServicesTime['tripTime'] = df_ptServicesTime['arrTime'] - df_ptServicesTime['depTime']

	return df_ptServicesTime
	

def export_df_to_csv(df, output_dir, scenario_name):
	
	suffix = '.csv'
	file_name = 'df_ptServices_baseline_vs_' + scenario_name
	filepath = os.path.join(output_dir, file_name + suffix)
	
	print('# Exporting file to: ', filepath)

	df.to_csv(filepath, index=False, sep=';')

	print('# Exported succesfully')
	

def main(baseline_events_filepath: str, scenario_events_filepath:str, scenario_name:str, output_dir_filepath: str):
	
	baseline_events = Path(baseline_events_filepath)
	scenario_events = Path(scenario_events_filepath)
	output_dir = Path(output_dir_filepath)
	
	# Check if input files exist:
	print('\n* Checking if input files exist:')
	Input_filePaths_list = [baseline_events, scenario_events]
	
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
	
	# Read the events files
	df_baseline_ptServices = ptServices_details(baseline_events)
	df_scenario_ptServices = ptServices_details(scenario_events)
	
	# rename some of the columns:
	df_baseline_ptServices.rename(columns={'depTime': 'B_depTime', 'arrTime': 'B_arrTime', 'tripTime': 'B_tripTime'}, inplace=True)
	df_scenario_ptServices.rename(columns={'depTime': 'S_depTime', 'arrTime': 'S_arrTime', 'tripTime': 'S_tripTime'}, inplace=True)

	# Combine both dataframes
	df_ptServices_comp = df_baseline_ptServices.merge(df_scenario_ptServices, on=['vehicle_id', 'transitLine_id', 'transitRoute_id'], how='outer')
	
	# Calculate the trip difference for each pt service route
	df_ptServices_comp['ServiceTime_DIFF'] = df_ptServices_comp['S_tripTime'] -  df_ptServices_comp['B_tripTime']
	
	# Export the data as csv
	export_df_to_csv(df_ptServices_comp, output_dir, scenario_name)
	
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
		output_dir_filepath=args.output_dir_filepath
	)