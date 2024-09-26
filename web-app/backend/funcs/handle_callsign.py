from bs4 import BeautifulSoup
import pandas as pd


def process_aircraft_callsigns(input_file: str, output_file: str, testing_file:str):
	# Read the HTML content from the file
	with open(input_file, 'r', encoding='utf-8') as file:
		html_content = file.read()

	# Parse the HTML content
	soup = BeautifulSoup(html_content, 'html.parser')
	table = soup.find('table', {'class': 'wikitable'})

	# Load table into a pandas DataFrame
	df = pd.read_html(str(table))[0]

	# Drop the 'Country/Region', 'IATA', and 'Comments' columns
	df = df.drop(columns=['Country/Region', 'IATA'])

	# Drop rows where 'Call sign' is empty
	df = df[df['Call sign'].notna() & (df['Call sign'] != '')]

	# Process the 'Call sign' to remove anything after '|' and capitalize the first letter of each word
	df['Call sign'] = df['Call sign'].apply(lambda x: x.split('|')[0].title().strip())

	# Drop rows where 'ICAO' is empty or has more than 3 letters
	df = df[df['ICAO'].notna() & (df['ICAO'].apply(lambda x: len(str(x)) == 3))]

	# Drop rows where 'Comments' contain 'Ceased operations' or 'defunct'
	df = df[~df['Comments'].str.contains('Ceased operations|defunct', case=False, na=False)]

	df = df[~df['Call sign'].str.contains('multiple', case=False, na=False)]

	# Drop the 'Comments' column now that we've used it for filtering
	df = df.drop(columns=['Comments'])

	df = df.rename(columns={'Call sign': 'Callsign'})

	# Save the DataFrame in Parquet format
	df.to_parquet(output_file, index=False)
	df.to_parquet(testing_file, index=False)

	return df


# Example usage (optional, for testing)
if __name__ == "__main__":
	df = process_aircraft_callsigns('./aircraft_callsign.txt', './aircraft_callsign.parquet','../tests/aircraft_callsign.parquet')
