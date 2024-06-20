import os
import pandas as pd

# TODO: Put paths in env file
input_dir = "cityCAT_example_data/"
output_xml = "test.xml"

# TODO: Put params in config file
water_depth_list = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
trigger_times = ["16:20:00", "16:40:00", "17:00:00", "17:20:00", "17:40:00", "18:00:00"]
freespeed_update_list = [0.7, 0.45, 0.3, 0.2, 0.15, 0.1]
column_categories = [9999, 0.50, 0.45, 0.40, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10, 0.05]
value_column = "value_agg"


def write_headers(file):
    file.write(f'<?xml version="1.0" encoding="UTF-8"?>\n')
    file.write(
        f'<networkChangeEvents xmlns="http://www.matsim.org/files/dtd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.matsim.org/files/dtd http://www.matsim.org/files/dtd/networkChangeEvents.xsd">\n\n')


def write_starttime(file, text):
    file.write(f'<networkChangeEvent startTime="{text}">\n')


def write_link(file, text):
    file.write(f'<link refId="{text}"/>\n')


def write_scalefactor(file, text):
    file.write(f'<freespeed type="scaleFactor" value="{text}"/>\n')


def load_df(filepath, column):
    df = pd.read_csv(filepath)
    df = df[['ID', column]]
    df[column] = df[column].astype('category')
    df[column] = df[column].cat.set_categories(column_categories, ordered=True)
    df.sort_values(['ID', column], inplace=True, ascending=True)
    return df


def unique_df(df):
    df_unique = df.drop_duplicates('ID')
    return df_unique[df_unique['ID'].notna()]


def main():
    with open(output_xml, "w") as writefile:
        write_headers(writefile)

        for i, csv_file in enumerate(os.listdir(input_dir)):
            filepath = input_dir + csv_file
            print('Processing file: ' + filepath)

            df_links_flooded = load_df(filepath, value_column)
            df_links_flooded_unique = unique_df(df_links_flooded)

            # Set initial starting time for this event stage
            trigger_time = trigger_times[i]

            for j, water_depth in enumerate(water_depth_list):
                write_starttime(writefile, trigger_time)
                df_unique_waterdepth = df_links_flooded_unique.loc[
                    df_links_flooded_unique[value_column] == water_depth]

                for k, depth in df_unique_waterdepth.iterrows():
                    link_flooded = depth['ID']
                    write_link(writefile, link_flooded)

                write_scalefactor(writefile, freespeed_update_list[j])
                writefile.write(f'</networkChangeEvent>\n')

                # Trigger time offset by 1 second for next set of water depths -
                #  all changes should happen at the same time for all water
                #  depths (i.e. write_starttime(writefile, triggertimes[i]),
                #  however this leads to an eventual MATSim error
                trigger_time = trigger_time[:7] + str(j + 1)

        writefile.write(f'</networkChangeEvents>\n')

    print('END')


if __name__ == "__main__":
    main()