import xml.etree.ElementTree as ET
from pathlib import Path
import pandas as pd
import csv
import argparse
import os
import gzip


###########################################################################################################

# Python code to identify the vehicles using at least one of the specified network link IDs

### This information is useful to know who are the vehicles that will need to adapt their behaviours once the previous two links are no longer in use (partially or totally).

## Output:

## CSV file containg information about the vehicle id, time when the vehicle enters the link and travel direction (e.g. NB, SB, WB, EB), which is provided by the user as an input.
## --> Column names: time_seconds, vehicle, travel_direction


###########################################################################################################


def identify_agents_using_links(xml_filepath, dataframe_output_filepath, scenario_name, link_1, link_1_dir, link_2, link_2_dir):

	
	# Create empty lists. One for network link direction:
	## link_13476 NB
	## link_125708 SB
	list_link1 = []
	list_link2 = []

	print('The links to be checked are: ' + link_1 + ' (' + link_1_dir + ')' +' and ' + link_2 + ' (' + link_2_dir + ')')

	print('Events file to be processed: ' + str(xml_filepath))

	print('Scenario name: ' + scenario_name)

	print('Output directory: ' + str(dataframe_output_filepath))

	print('Unzipping and opening Events file now...')

	xml_input = gzip.open(xml_filepath, 'rb')
	MATSim_events = ET.parse(xml_input)
	root = MATSim_events.getroot()
	
	print('Processing the Events file now...')
	

	for child in root:

		type_event = (child.attrib['type'])
  
		if (type_event == 'entered link'):

			link = (child.attrib['link'])

			if (link == link_1):

				temp_list = []

				time = (child.attrib['time'])
				vehicle = (child.attrib['vehicle'])
				#networkMode = (child.attrib['networkMode'])

				temp_list.append(time)
				temp_list.append(vehicle)
				#temp_list.append(networkMode)
				temp_list.append(link_1_dir)

				list_link1.append(temp_list)

			if (link == link_2):

				temp_list = []

				time = (child.attrib['time'])
				vehicle = (child.attrib['vehicle'])
				#networkMode = (child.attrib['networkMode'])
 
				temp_list.append(time)
				temp_list.append(vehicle)
				#temp_list.append(networkMode)
				temp_list.append(link_2_dir)

				list_link2.append(temp_list)


	# Combine both list:
	joinedlist = list_link1 + list_link2

	# Save the list as a dataframe, with specific column names: 
	df_agents_using_TyneBridge = pd.DataFrame(joinedlist, columns=["time_seconds", "vehicle", "travel_direction"])
	
	# Define the name of the output file
	##output_dir = dataframe_output_filepath + scenario_name + '.csv'

	output_dir = os.path.join(dataframe_output_filepath, scenario_name + '.csv' )

	# Export the data to a csv
	df_agents_using_TyneBridge.to_csv(output_dir, index=False, sep=';') 


	print('Process has finished. Check the results, amigo!')




def main(xml_filepath: str, dataframe_output_filepath: str, scenario_name: str, link_1: str, link_1_dir: str, link_2: str, link_2_dir: str):

	xml_filepath = Path(xml_filepath)
	dataframe_output_filepath = Path(dataframe_output_filepath)

	identify_agents_using_links(xml_filepath, dataframe_output_filepath, scenario_name, link_1, link_1_dir, link_2, link_2_dir)



if __name__ == "__main__":
	p = argparse.ArgumentParser()

	p.add_argument(
	'--xml_filepath',
	required=True,
	type=str
	)

	p.add_argument(
	'--dataframe_output_filepath',
	required=True,
	type=str
	)

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


	args = p.parse_args()

	main(
		xml_filepath=args.xml_filepath,
		dataframe_output_filepath=args.dataframe_output_filepath,
		scenario_name=args.scenario_name,
		link_1=args.link_1,
		link_1_dir=args.link_1_dir,
		link_2=args.link_2,
		link_2_dir=args.link_2_dir,	 
	)
