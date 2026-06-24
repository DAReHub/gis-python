import pandas as pd
import numpy as np
import os
import csv
import argparse
from pathlib import Path
import gzip
import xml.etree.ElementTree as ET
import sys


###########################################################################################################

# Python code to extract information from EVENTS files comparing how some PRESELECTED agents behave in the baseline and a specific scenario.

## Outputs (6 CSV files):
## CSV file containing all network links used by the preselected agents in the baseline
## --> Columns name: person;vehicle_id;trip_id;link_id;time_id

## CSV file containing all network likes used by the preselected agents in the scenario
## --> Columns name: person;vehicle_id;trip_id;link_id;time_id

## CSV file containing only the links that the agent followed in the baseline that were not used in the scenario
## --> Columns name: person;vehicle_id;trip_id;link_id;time_id

## CSV file containing only the links that the agent followed in the scenario that were not used in the baseline
# --> Columns name: person;vehicle_id;trip_id;link_id;time_id

## CSV file containing only the links that the agent used in a specific trip (i.e. the one that used specific network links) during the baseline and not during the scenario
# --> Columns name: vehicle_id_x;link_id_x;trip_id;time_id;Direction

## CSV file containing only the links that the agent used in a specific trip (i.e. the one(s) that used specific network links) during the scenario and not during the baseline
# --> Columns name: vehicle_id_x;link_id_x;trip_id;time_id;Direction

###########################################################################################################





def read_csv(path):

	print('# Importing file...')

	df_simulation = pd.read_csv(path, index_col=None, header=0, delimiter=";")

	print('# File imported')

	return df_simulation



def potential_baseline_crossing_users(df):
	
	df_bus = df.loc[df['vehicle'].str.contains('bus')]
	bus_list = df_bus['vehicle'].unique().tolist()
	
	df_NoBus = df.loc[~(df['vehicle'].str.contains('bus'))].copy()
	# Create a new column with the person ID
	df_NoBus["person"] = df_NoBus["vehicle"].str.split("_").str[:2].str.join("_")
	
	df_NoBus['person_car_passenger'] = df_NoBus['person'] + '_car_passenger'
	df_NoBus['person_bike'] = df_NoBus['person'] + '_bike'
	
	vehicleBike_list = df_NoBus['person_bike'].unique().tolist()
	vehicleCarPass_list = df_NoBus['person_car_passenger'].unique().tolist()
	vehicleCar_list = df_NoBus['person'].unique().tolist()
	
	potentialVehicleUsers = vehicleCar_list + vehicleCarPass_list + vehicleBike_list + bus_list
	
	return potentialVehicleUsers
	
	


def matsim_events_reader(agents_list, events_file, output_dir):

	# read events file
	print('# Decompressing zip file ...')
		
	xml_input = gzip.open(events_file, 'rb')
	
	print('# Opening EVENTS file ...')
	
	MATSim_events = ET.parse(xml_input)
	root = MATSim_events.getroot()

	# create empty list to store data later
	agents_routeLink_time_list = []


	print('# Reading and identifying the road links used by the previous identified agents...')

	for child in root:
		
		type_event = (child.attrib['type'])
		
		if ((type_event == 'entered link') or (type_event == 'vehicle enters traffic')):
			
			vehicle = (child.attrib['vehicle'])
			
			if (vehicle in agents_list):

				temp_list = []
			
				vehicle_id = (child.attrib['vehicle'])
				link_id = (child.attrib["link"])
				time_id = (child.attrib["time"])

				temp_list.append(vehicle_id)
				temp_list.append(link_id)
				temp_list.append(time_id)
				
				agents_routeLink_time_list.append(temp_list)


	print('# Road links identified')

	# sort the lists by first element ('vehicle_id') 
	agents_routeLink_time_list = sorted(agents_routeLink_time_list, key=lambda x:x[0])
	
	# Create a datafrane
	df_agents_ALL_routeLink_time = pd.DataFrame(agents_routeLink_time_list)
	
	df_agents_ALL_routeLink_time.columns =['vehicle_id','link_id', 'time_id']
	
	# Create a dataframe containing only bus routes
	df_bus_routesOnly = df_agents_ALL_routeLink_time.loc[df_agents_ALL_routeLink_time['vehicle_id'].str.contains('bus')]
	
	# Export the dataframe as csv
	print('Exporting bus routes using the closed crossing in the baseline.')
	export_df_to_csv(df_bus_routesOnly, output_dir)
	

	# Create a new column with the person ID
	df_agents_ALL_routeLink_time["person"] = df_agents_ALL_routeLink_time["vehicle_id"].str.split("_").str[:2].str.join("_")

	
	return df_agents_ALL_routeLink_time



def time_convert(x):
	h,m,s = map(int,x.split(':'))
	time_seconds = int(h) *3600 +int(m)*60 + int(s)
	return int(float(time_seconds))




# Identify those elements from list_1 that are not in list_2
def add_trip_id_to_links(df_routes, df_trips, output_dir):
	
	df_trips['dep_time'] = df_trips['dep_time'].astype(str)
	df_trips['trav_time'] = df_trips['trav_time'].astype(str)

	
	# Update the dep_time and trav_time columns to seconds
	df_trips['dep_time'] = df_trips.dep_time.apply(time_convert)
	df_trips['trav_time'] = df_trips.trav_time.apply(time_convert)
	# Create a new column for the arrival time of each trip
	df_trips['arr_time'] = df_trips['dep_time'] + df_trips['trav_time']
	

	# Keep only relevant columns
	df_trips = df_trips[['person', 'trip_id', 'dep_time', 'arr_time']]

	# Create a new column with the person id
	#df_routes["person"] = df_routes["vehicle_id"].str.split("_").str[:2].str.join("_")

	# Merge both dataframes 'many-to-many'
	df = pd.merge(df_routes, df_trips, on='person', validate = 'many_to_many')
	
	df['time_id'] = df['time_id'].astype(float).astype(int)

	# Keep only those columns where 'time_id' is between 'dep_time' and 'arr_time'
	df = df[(df.time_id >= df.dep_time) & (df.time_id <= df.arr_time)]

	# keep only relevant columns
	df = df[['person', 'vehicle_id', 'trip_id', 'link_id', 'time_id']]
	
	print('Exporting road links as csv')
	# Export the dataframe as csv file:
	export_df_to_csv(df, output_dir)
	
	return df

	



# Identify those elements from list_1 that are not in list_2
def compare_links(df_routes1, df_routes_2):

	print('Identifying the different followed links')

	# Merge both dataframes based on columns: 'vehicle_id','link_id' and 'trip_id'
	# Use the parameter indicator to return an extra column indicating which table the row was from ('left_only', 'right_only', 'both')
	df_all = df_routes1.merge(df_routes_2.drop_duplicates(), on=['vehicle_id','link_id','trip_id'], 
				   how='left', indicator=True)
				   
	#print(df_all.head(1))
	#sys.exit()

	# If value is 'left_only' it means that df_routes1 row was not matched with anything from df_routes2
	df_different_used_links = df_all.loc[(df_all['_merge'] == 'left_only')].copy()
	
	# keep only relevant columns
	df_different_used_links = df_different_used_links[['person_x', 'vehicle_id', 'trip_id', 'link_id', 'time_id_x']]
	
	# rename some of the columns:
	df_different_used_links.rename(columns={'person_x': 'person', 'trip_id_x': 'trip_id', 'time_id_x': 'time_id', }, inplace=True)


	print('Identified')

	return df_different_used_links



def keep_TB_altered_trips_only(df, df_baseline_trips_altered_TB_link, scenario_altered_trips_only_output, df_routeLinks, link_1, link_1_dir, link_2, link_2_dir):

	# Get the trip_id values that containg the Tyne Bridge links
	trips_altered_list = df_baseline_trips_altered_TB_link['trip_id'].unique().tolist()

	# Create a new attribute to identify if the baseline trip using the TB is NB or SB
	df_baseline_trips_altered_TB_link['Direction']  = ''
	
	df_baseline_trips_altered_TB_link['Direction'] = df_baseline_trips_altered_TB_link['Direction'].mask(df_baseline_trips_altered_TB_link.link_id == link_1, link_1_dir).mask(df_baseline_trips_altered_TB_link.link_id == link_2, link_2_dir)
	
	#print(df_baseline_trips_altered_TB_link)
	
	# Get those trips in the baseline that used the TyneBridge in the baseline	
	## In the scenario, agents followed an alternative route
	df_scenario_trips_altered_TB_link = df.loc[(df['trip_id'].isin(trips_altered_list))].copy()

	#print(df_scenario_trips_altered_TB_link)
	
	# Include the "Direction" attribute into the scenario dataframe
	df_scenario_trips_altered_TB_link_dir = df_scenario_trips_altered_TB_link.merge(df_baseline_trips_altered_TB_link, on=['trip_id'], how='left')


	#print(df_scenario_trips_altered_TB_link_dir)

	# Include the time where the agents enter in each link from the df_routeLinks
	df_scenario_trips_altered_TB_link_time = pd.merge(left=df_scenario_trips_altered_TB_link_dir, right=df_routeLinks, how='left',left_on=['vehicle_id_x', 'link_id_x'], right_on=['vehicle_id', 'link_id'])

	# Keep only the relevant columns:
	df_scenario_trips_altered_TB_link_time = df_scenario_trips_altered_TB_link_time[['vehicle_id_x', 'link_id_x', 'trip_id', 'time_id', 'Direction']]

	#print(df_scenario_trips_altered_TB_link_time)



	# Export the dataframe as csv
	print('Exporting ONLY the modified trips in the scenario with the time entering each link and the direction followed when using the Tyne Bridge in baseline.')
	export_df_to_csv(df_scenario_trips_altered_TB_link_time, scenario_altered_trips_only_output)
	




def export_df_to_csv(df, output_dir):

	print('# Exported to: ', output_dir)

	df.to_csv(output_dir, index=False, sep=';')

	print('# Exported succesfully')




def main(scenario_name: str, link_1: str, link_1_dir: str, link_2: str, link_2_dir: str, baseline_CrossingUsers_filepath: str, 
	scenario_events_filepath: str, baseline_events_filepath: str, scenario_trips_filepath: str, baseline_trips_filepath: str, 
	scenario_bus_routes_filepath:str, baseline_bus_routes_filepath:str, new_linksFollowed_filepath: str, old_linksFollowed_filepath : str, 
	scenario_chosen_agents_all_routes_filepath: str, baseline_chosen_agents_all_routes_filepath : str, 
	new_linksFollowed_avoidingCrossing_Only_filepath: str, old_linksFollowed_usingCrossingBaseline_Only_filepath: str):
	
	# REQUIRED INPUTS IN COMMAND LINE:: str, 
	## INPUTS:
	baseline_TB_usersID = Path(baseline_CrossingUsers_filepath)
	matsim_events_scenario = Path(scenario_events_filepath)
	matsim_events_baseline = Path(baseline_events_filepath)
	scenario_trips = Path(scenario_trips_filepath)
	baseline_trips = Path(baseline_trips_filepath)

	## OUTPUTS:
	Scenario_bus_routes_output = Path(scenario_bus_routes_filepath)
	Baseline_bus_routes_output = Path(baseline_bus_routes_filepath)
	new_routes_followed_output = Path(new_linksFollowed_filepath)
	old_routes_followed_output = Path(old_linksFollowed_filepath)
	scenario_chosen_agents_all_routes_output = Path(scenario_chosen_agents_all_routes_filepath)
	baseline_chosen_agents_all_routes_output = Path(baseline_chosen_agents_all_routes_filepath)
	scenario_altered_trips_time_links_output = Path(new_linksFollowed_avoidingCrossing_Only_filepath)
	baseline_trips_usingTB_time_links_output = Path(old_linksFollowed_usingCrossingBaseline_Only_filepath)
		
	
	# Initial message indicating the Scenario name and the agents which are going to be analysed, based on the 
	print('')
	print('###################################################################')
	print('* Analysis of ' + scenario_name + '. Links closed: link ' + link_1 + ' (' + link_1_dir + ' direction) and link '  + link_2 + ' (' + link_2_dir + ' direction)' )
	print('* This analysis identifies \n\t(1) the alternative routes followed by the agents and Public Transport services (e.g., bus, rail, metro) impacted by the ' + scenario_name + ' scenario and \n\t(2) their original routes followed in the baseline. \n')
	
	# Check if input files exist:
	print('* Checking if input files exist:')
	
	Input_filePaths_list = [baseline_TB_usersID, matsim_events_scenario, matsim_events_baseline, scenario_trips, baseline_trips]
	
	for inputPath in Input_filePaths_list:
		if inputPath.exists():
			print('File ' + str(inputPath) + ' found.')
		else:
			print('\n*** File ' + str(inputPath) + ' was not found!. Check if the given path is correct and exists.\n')
			sys.exit()
	
	# Check if output directories exist (not the files):
	print('\n* Checking if output directories exist:')
	
	Output_filePaths_list = [new_routes_followed_output, old_routes_followed_output, scenario_chosen_agents_all_routes_output, baseline_chosen_agents_all_routes_output, scenario_altered_trips_time_links_output, baseline_trips_usingTB_time_links_output]
	
	for outputFile in Output_filePaths_list:
		directory = os.path.dirname(os.path.realpath(outputFile))
		directoryPath = Path(directory)
		
		if directoryPath.exists():
			print('Directory ' + str(directoryPath) + ' found.')
		else:
			print('\n*** Directory ' + str(directoryPath) + ' was not found!. Check if the given directory is correct and exists.\n')
			sys.exit()
	
	print('\n* Input files and output directories succesfully identified!\n\n')
	
	# Read the agents using the TB in both scenario and baseline
	print('Importing file: ' + str(baseline_TB_usersID) + ' with information about the agents using the closed crossing: (' + scenario_name + ') in the baseline.')
	df_baseline_Crossing_users = read_csv(baseline_TB_usersID)

	# Get the agentsID of those that use the "Crossing" under analysis in the baseline but do not in the scenario. All other potential users (*_bike, *_car_passenger and *(car) need to be added to find them in the Scenario Events, as some agents might have changed the transport mode used!)
	potentialVehicleUsers_list = potential_baseline_crossing_users(df_baseline_Crossing_users)
	
	# Get the links used by the agents chosen in potentialVehicleUsers_list
	print('Proccessing MATSim ' + scenario_name + ' Events file... ' + str(matsim_events_scenario))
	df_scenario_routeLinks = matsim_events_reader(potentialVehicleUsers_list, matsim_events_scenario, Scenario_bus_routes_output)
	print('Proccessing MATSim BASELINE Events file... ' + str(matsim_events_baseline))
	df_baseline_routeLinks = matsim_events_reader(potentialVehicleUsers_list, matsim_events_baseline, Baseline_bus_routes_output)

	# Read the agents trips:
	print('Importing file: ' + str(scenario_trips) + ' with ALL simulated trips from: ' + scenario_name)
	df_scenario_trips = read_csv(scenario_trips)
	print('Importing file: ' + str(baseline_trips) + ' with ALL simulated trips from the baseline.')
	df_baseline_trips = read_csv(baseline_trips)

	# Clean and update route dataframes, departure and arrival as seconds and new column with the trip_id to which each link belongs in the trips file
	df_scenario_routeTrips_updated = add_trip_id_to_links(df_scenario_routeLinks, df_scenario_trips, scenario_chosen_agents_all_routes_output)
	df_baseline_routeTrips_updated = add_trip_id_to_links(df_baseline_routeLinks, df_baseline_trips, baseline_chosen_agents_all_routes_output)

	# Compare the links used by the agents in scenario and baseline
	## Those links used in the scenario but not in the baseline:
	df_new_used_links_in_scenario = compare_links(df_scenario_routeTrips_updated, df_baseline_routeTrips_updated)

	## Those links used in the baseline but not in the scenario:
	df_old_used_links_in_baseline = compare_links(df_baseline_routeTrips_updated, df_scenario_routeTrips_updated)

	# Export datasets as csv files:
	print('New ALL followed road links in scenario exported as csv')
	export_df_to_csv(df_new_used_links_in_scenario, new_routes_followed_output)
	print('Old ALL followed links in baseline exported as csv')
	export_df_to_csv(df_old_used_links_in_baseline, old_routes_followed_output)
	
	# Identify the rows using the closed crossing links
	df_baseline_trips_using_closedBridge = df_old_used_links_in_baseline.loc[((df_old_used_links_in_baseline['link_id'] == link_1) | (df_old_used_links_in_baseline['link_id'] == link_2))].copy()

	# These are the new links used by the agents to avoid the Tyne Bridge
	keep_TB_altered_trips_only(df_new_used_links_in_scenario, df_baseline_trips_using_closedBridge, scenario_altered_trips_time_links_output, df_scenario_routeLinks, link_1, link_1_dir, link_2, link_2_dir)

	# These are the links used by the agents in baseline when using the Tyne
	keep_TB_altered_trips_only(df_old_used_links_in_baseline, df_baseline_trips_using_closedBridge, baseline_trips_usingTB_time_links_output, df_baseline_routeLinks, link_1, link_1_dir, link_2, link_2_dir)

	
	print('Process has finished. Check the results, amigo!')


if __name__ == "__main__":
	p = argparse.ArgumentParser()

	p.add_argument(
		'--scenario_name',
		required=True,
		type=str
	)
	
	p.add_argument(
		'--link_1',
		required=True,
		type=str
	)

	p.add_argument(
		'--link_1_dir',
		required=True,
		type=str
	)

	p.add_argument(
		'--link_2',
		required=True,
		type=str
	)

	p.add_argument(
		'--link_2_dir',
		required=True,
		type=str
	)
	
	p.add_argument(
		'--baseline_CrossingUsers_filepath',
		required=True,
		type=str
	)

	p.add_argument(
		'--scenario_events_filepath',
		required=True,
		type=str
	)

	p.add_argument(
		'--baseline_events_filepath',
		required=True,
		type=str
	)

	p.add_argument(
		'--scenario_trips_filepath',
		required=True,
		type=str
	)

	p.add_argument(
		'--baseline_trips_filepath',
		required=True,
		type=str
	)

	p.add_argument(
		'--scenario_bus_routes_filepath',
		required=True,
		type=str
	)
	
	p.add_argument(
		'--baseline_bus_routes_filepath',
		required=True,
		type=str
	)
	
	p.add_argument(
		'--new_linksFollowed_filepath',
		required=True,
		type=str
	)

	p.add_argument(
		'--old_linksFollowed_filepath',
		required=True,
		type=str
	)

	p.add_argument(
		'--scenario_chosen_agents_all_routes_filepath',
		required=True,
		type=str
	)

	p.add_argument(
		'--baseline_chosen_agents_all_routes_filepath',
		required=True,
		type=str
	)

	p.add_argument(
		'--new_linksFollowed_avoidingCrossing_Only_filepath',
		required=True,
		type=str
	)

	p.add_argument(
		'--old_linksFollowed_usingCrossingBaseline_Only_filepath',
		required=True,
		type=str
	)

	args = p.parse_args()


	main(
		scenario_name=args.scenario_name,
		link_1=args.link_1,
		link_1_dir=args.link_1_dir,
		link_2=args.link_2,
		link_2_dir=args.link_2_dir,
		baseline_CrossingUsers_filepath=args.baseline_CrossingUsers_filepath,
		scenario_events_filepath=args.scenario_events_filepath,
		baseline_events_filepath=args.baseline_events_filepath,
		scenario_trips_filepath=args.scenario_trips_filepath,
		baseline_trips_filepath=args.baseline_trips_filepath,
		scenario_bus_routes_filepath=args.scenario_bus_routes_filepath,
		baseline_bus_routes_filepath=args.baseline_bus_routes_filepath,
		new_linksFollowed_filepath=args.new_linksFollowed_filepath,
		old_linksFollowed_filepath=args.old_linksFollowed_filepath,
		scenario_chosen_agents_all_routes_filepath=args.scenario_chosen_agents_all_routes_filepath,
		baseline_chosen_agents_all_routes_filepath=args.baseline_chosen_agents_all_routes_filepath,
		new_linksFollowed_avoidingCrossing_Only_filepath = args.new_linksFollowed_avoidingCrossing_Only_filepath,
		old_linksFollowed_usingCrossingBaseline_Only_filepath = args.old_linksFollowed_usingCrossingBaseline_Only_filepath
	)

