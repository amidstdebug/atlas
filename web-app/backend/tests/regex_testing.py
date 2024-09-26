# test_transcription.py
import pytest
from ..funcs.transcription import apply_custom_fixes
import logging


# Suppress logging during testing to keep test output clean
@pytest.fixture(autouse=True)
def disable_logging():
	logging.disable(logging.CRITICAL)
	yield
	logging.disable(logging.NOTSET)


# ============================
# Define test cases as tuples of (input, expected_output)
# ============================

test_cases = [
	# ============================
	# Basic Test Cases (1-17)
	# ============================
	# 1. Remove Whisper Artifacts
	(
		"This is the transcript. Thanks for watching.",
		"This is the transcript."
	),
	# 3. Standardize Units (Feet and Knots)
	(
		"We are at five hundred feet and traveling at one hundred knots.",
		"We are at 500ft and traveling at 100kts."
	),
	# 4. Standardize Directions
	(
		"Turn left heading two hundred and thirty degrees.",
		"Turn left heading 230 degrees."
	),
	# 5. Apply Word-to-Number Mapping
	(
		"Flight level three five zero",
		"FL350"
	),
	# 6. Capitalize NATO Words and First Word
	(
		"alpha bravo charlie",
		"Alpha Bravo Charlie"
	),
	# 7. Combine Adjacent Digits for Callsigns
	(
		"Call sign one two three four",
		"Call sign 1234"
	),
	# 8. Handle Flight Levels
	(
		"Flight level three five zero",
		"FL350"
	),
	# 9. Handle Squawk Codes
	(
		"Squawk one two three four",
		"Squawk 1234"
	),
	# 10. Combine Numbers with Units
	(
		"Two five zero feet and one zero zero",
		"250ft and 100"
	),
	# 11. Handle Decimal Follow-ups
	(
		"Altitude three five zero point zero one two",
		"Altitude 350.012"
	),
	# 12. Handle 'Word + Digits' Patterns
	(
		"Taxiway A 1",
		"Taxiway A1"
	),
	# 13. Combine Remaining Adjacent Digits
	(
		"Runway one two L",
		"Runway 12L"
	),
	# 14. Validate False Activations (Repeated Words)
	(
		"you you you you",
		"False activation"
	),
	# 15. Validate False Activations (Short Phrases)
	(
		"thank you very much",
		"False activation"
	),
	# 16. Capitalize First Word
	(
		"golf hotel india",
		"Golf Hotel India"
	),

	# ============================
	# Advanced Test Cases (18-67)
	# ============================
	# 18. Combined Units and Directions
	(
		"We are climbing to five thousand feet heading to the right three five degrees.",
		"We are climbing to 5000ft heading to the right 35 degrees."
	),
	# 19. Multiple Flight Levels
	(
		"Climbing to flight level three five zero then to flight level four zero zero.",
		"Climbing to FL350 then to FL400."
	),
	# 20. Multiple Squawk Codes
	(
		"Set squawk one two three four and prepare for squawk five six seven eight.",
		"Set squawk 1234 and prepare for squawk 5678."
	),
	# 21. Callsign and Flight Level
	(
		"Call sign alpha one two three four, flight level three five zero.",
		"Call sign Alpha 1234, FL350."
	),
	# 22. NATO Words with Directions
	(
		"Alpha bravo, turn left heading one two zero degrees and maintain flight level three five zero.",
		"Alpha Bravo, turn left heading 120 degrees and maintain FL350."
	),
	# 24. Combined Flight Level and Squawk
	(
		"Climb to flight level three five zero and set squawk one two three four.",
		"Climb to FL350 and set squawk 1234."
	),
	# 25. Multiple Units and Squawks
	(
		"Maintain two thousand feet and squawk five six seven eight.",
		"Maintain 2000ft and squawk 5678."
	),
	# 26. Combined Directions and Units
	(
		"Turn right three zero degrees and climb to five thousand feet.",
		"Turn right 30 degrees and climb to 5000ft."
	),
	# 28. Runway and Taxiway Combination
	(
		"Taxi to taxiway alpha one and then to runway one two left.",
		"Taxi to taxiway Alpha 1 and then to runway 12L."
	),
	# 29. Complex Sentence with Multiple Transformations
	(
		"We are at twenty five zero feet, climbing to flight level four zero zero, squawk one two three four, and heading north.",
		"We are at 250ft, climbing to FL400, squawk 1234, and heading north."
	),
	# 30. Multiple Units and Flight Levels
	(
		"Maintain five thousand feet, then climb to flight level four zero zero.",
		"Maintain 5000ft, then climb to FL400."
	),
	# 31. Multiple Directions and Units
	(
		"Descend to three thousand feet, turn left fifteen degrees, and maintain flight level three five zero.",
		"Descend to 3000ft, turn left 15 degrees, and maintain FL350."
	),
	# 32. Combined Words and Numbers
	(
		"Route is victor one two three four five, squawk zero zero zero one.",
		"Route is Victor 12345, squawk 0001."
	),
	# 33. Complex Decimal Handling
	(
		"Altitude one zero zero point zero zero one.",
		"Altitude 100.001."
	),
	# 34. Multiple Callsigns
	(
		"Call sign alpha one two three four and call sign bravo five six seven eight.",
		"Call sign Alpha 1234 and call sign Bravo 5678."
	),
	# 35. Units and Directions with NATO Words
	(
		"Maintain one zero zero feet and turn to the left twenty degrees.",
		"Maintain 100ft and turn to the left 20 degrees."
	),
	# 36. Multiple Flight Levels and Units
	(
		"Climbing to flight level three five zero feet and then to flight level four zero zero feet.",
		"Climbing to FL350ft and then to FL400ft."
	),
	# 37. Combining Adjacent Digits and Units
	(
		"We are at one two five feet and moving at one zero zero knots.",
		"We are at 125ft and moving at 100kts."
	),
	# 38. Callsign with Directions
	(
		"Call sign alpha one two three four, turn right thirty degrees.",
		"Call sign Alpha 1234, turn right 30 degrees."
	),
	# 39. Multiple Squawks in One Transcription
	(
		"Set squawk one two three four and later squawk five six seven eight.",
		"Set squawk 1234 and later squawk 5678."
	),
	# 40. Complex Transformation with Multiple Patterns
	(
		"We are at twenty five hundred feet, climbing to flight level three five zero, squawk one two three four, and heading west.",
		"We are at 2500ft, climbing to FL350, squawk 1234, and heading west."
	),
	# 41. Multiple Units and Flight Levels
	(
		"Climbing to flight level three five zero, then descend to two thousand feet.",
		"Climbing to FL350, then descend to 2000ft."
	),
	# 42. Multiple Directions and Units
	(
		"Turn left one two zero degrees, then right three zero degrees, and climb to two five zero feet.",
		"Turn left 120 degrees, then right 30 degrees, and climb to 250ft."
	),
	# 44. Complex Callsign and Flight Level
	(
		"Call sign alpha one two three four, flight level three five zero.",
		"Call sign Alpha 1234, FL350."
	),
	# 45. Multiple Numbers with Units
	(
		"Altitude three zero zero feet and speed one zero zero knots.",
		"Altitude 300ft and speed 100kts."
	),
	# 46. Multiple Transformations with NATO Words
	(
		"Alpha bravo, turn left one two zero degrees and maintain altitude three five zero feet.",
		"Alpha Bravo, turn left 120 degrees and maintain altitude 350ft."
	),
	# 47. Combined Directions and Flight Levels
	(
		"Turn right one five degrees, then climb to flight level three five zero.",
		"Turn right 15 degrees, then climb to FL350."
	),
	# 48. Callsign with Multiple Numbers
	(
		"Call sign alpha one two three four five six seven eight.",
		"Call sign Alpha 12345678."
	),
	# 50. Complex Callsign, Squawk, and Flight Level
	(
		"Call sign alpha one two three four, squawk one two three four, and climb to flight level three five zero.",
		"Call sign Alpha 1234, squawk 1234, and climb to FL350."
	),
	# 51. Multiple Units, Directions, and Numbers
	(
		"Maintain one thousand feet, turn right ten degrees, and set squawk one two three four.",
		"Maintain 1000ft, turn right 10 degrees, and set squawk 1234."
	),
	# 52. Combined Squawk and Flight Level
	(
		"Set squawk five six seven eight and climb to flight level four zero zero.",
		"Set squawk 5678 and climb to FL400."
	),
	# 53. Complex Runway and Taxiway
	(
		"Taxiway alpha one to runway one two left.",
		"Taxiway Alpha 1 to runway 12L."
	),
	# 54. Combined Units and Callsigns
	(
		"Maintain two five zero feet, call sign alpha one two three four.",
		"Maintain 250ft, call sign Alpha 1234."
	),
	# 55. Multiple Flight Levels and Directions
	(
		"Climb to flight level three five zero, then turn left twenty degrees.",
		"Climb to FL350, then turn left 20 degrees."
	),
	# 56. Combined Decimal and Units
	(
		"Altitude three five zero point five zero feet.",
		"Altitude 350.50ft."
	),
	# 57. Multiple Combined Transformations
	(
		"Call sign alpha one two three four, climb to flight level three five zero, squawk one two three four, and turn right thirty degrees.",
		"Call sign Alpha 1234, climb to FL350, squawk 1234, and turn right 30 degrees."
	),
	# 58. Combined Units, Directions, and Flight Level
	(
		"Maintain one thousand feet, turn left ten degrees, and climb to flight level three five zero.",
		"Maintain 1000ft, turn left 10 degrees, and climb to FL350."
	),
	# 59. Combined Numbers and NATO Words
	(
		"We are moving to taxiway alpha one and then to runway bravo two three left.",
		"We are moving to taxiway Alpha 1 and then to runway Bravo 23L."
	),
	# 60. Complex Decimal Handling and Units
	(
		"Altitude three five zero point one two feet.",
		"Altitude 350.12ft."
	),
	# 61. Combined Directions, Units, and Flight Level
	(
		"Turn right twenty degrees, descend to two thousand feet, and maintain flight level three five zero.",
		"Turn right 20 degrees, descend to 2000ft, and maintain FL350."
	),
	# 62. Combined Callsign, Squawk, and Directions
	(
		"Call sign alpha one two three four, squawk one two three four, turn left thirty degrees.",
		"Call sign Alpha 1234, squawk 1234, turn left 30 degrees."
	),
	# 63. Multiple Units, Directions, and Numbers
	(
		"Maintain one thousand feet, turn right ten degrees, and set squawk one two three four.",
		"Maintain 1000ft, turn right 10 degrees, and set squawk 1234."
	),
	# 64. Combined Flight Levels and Units
	(
		"Climbing to flight level three five zero and maintain two thousand feet.",
		"Climbing to FL350 and maintain 2000ft."
	),
	# 65. Combined Directions and Flight Levels
	(
		"Turn left twenty degrees, then climb to flight level three five zero.",
		"Turn left 20 degrees, then climb to FL350."
	),
	# 66. Complex Callsign and Directions
	(
		"Call sign alpha one two three four, turn right twenty degrees.",
		"Call sign Alpha 1234, turn right 20 degrees."
	),
	# 67. Combined Units, Flight Levels, and Squawks
	(
		"Maintain three thousand feet, climb to flight level four zero zero, and squawk one two three four.",
		"Maintain 3000ft, climb to FL400, and squawk 1234."
	),
	# Altitudes (Feet)
	("Climb to twelve hundred feet", "Climb to 1200ft"),
	("Descend to five hundred feet", "Descend to 500ft"),
	("Climb to twelve thousand feet", "Climb to 12000ft"),
	("Maintain flight level three fifty", "Maintain FL350"),
	("Descend to flight level two eighty", "Descend to FL280"),
	("Descend to three fifty feet", "Descend to 350ft"),

	# Headings and Directions
	("Turn left heading one eighty", "Turn left heading 180"),
	("Fly heading two seventy", "Fly heading 270"),
	("Maintain heading three sixty", "Maintain heading 360"),
	("Turn left to heading zero ninety", "Turn left to heading 090"),
	("Fly heading one twenty degrees", "Fly heading 120 degrees"),

	# Speed (Knots)
	("Maintain speed one fifty knots", "Maintain speed 150kts"),
	("Reduce speed to two forty knots", "Reduce speed to 240kts"),
	("Increase speed to one twenty knots", "Increase speed to 120kts"),
	("Maintain speed one hundred knots", "Maintain speed 100kts"),

	# Callsigns
	("American twelve three", "AAL123"),
	("Delta five sixty seven", "DAL567"),
	("Cessna four five nine", "Cessna 459"),
	("Air Force one", "Air Force 1"),
	("Navy six three", "NVY63"),

	# Runway Identifiers
	("Cleared for runway eighteen left", "Cleared for runway 18L"),
	("Taxi to runway twenty seven right", "Taxi to runway 27R"),
	("Line up and wait runway three six", "Line up and wait runway 36"),
	("Cleared to land runway twenty right", "Cleared to land runway 20R"),
	("Hold short of runway twenty left", "Hold short of runway 20L"),

	# Distances (Nautical Miles)
	("Descend to two thousand feet in five miles", "Descend to 2000ft in 5 miles"),
	("Maintain ten miles spacing", "Maintain 10 miles spacing"),
	("Turn right heading two twenty for twelve miles", "Turn right heading 220 for 12 miles"),

	# Time
	("Hold for five minutes", "Hold for 5 minutes"),
	("Expect approach in ten minutes", "Expect approach in 10 minutes"),
	("Estimated time of arrival sixteen thirty Zulu", "Estimated time of arrival 1630Z"),
	("Hold at the fix for four minutes", "Hold at the fix for 4 minutes"),

	# Clearances
	("Climb and maintain flight level two eighty", "Climb and maintain FL280"),
	("Descend and maintain six thousand feet", "Descend and maintain 6000ft"),
	("Maintain speed three hundred knots", "Maintain speed 300kts"),
	("Slow to two twenty knots", "Slow to 220kts"),
	("Fly heading three ten", "Fly heading 310"),
	("Turn right to heading two ten", "Turn right to heading 210"),

	# Squawk Codes
	("Squawk seven thousand", "Squawk 7000"),
	("Set squawk code twelve thirty four", "Set squawk code 1234"),

	# Miscellaneous
	("Southwest flight three oh seven", "Southwest flight 307"),
	("Delta flight four fifty six", "Delta flight 456"),
	("Wind two thirty at fifteen knots", "Wind 230 at 15kts"),
	("Maintain separation of three miles", "Maintain separation of 3 miles"),
	("Maintain ten thousand feet of separation", "Maintain 10000ft of separation"),
	# ("Maintain one zero ten thousand feet", "Maintain 10000ft"),

	("Flight level one fifty", "FL150"),
	("Climb to three thousand feet", "Climb to 3000ft"),
	("Reduce speed to one forty knots", "Reduce speed to 140kts"),
	("Heading one thirty degrees", "Heading 130 degrees"),
	("Descend to flight level three ten", "Descend to FL310"),
	("Squawk fifteen sixty seven", "Squawk 1567"),
	("Maintain heading two fifty", "Maintain heading 250"),
	("Descend and maintain four thousand feet", "Descend and maintain 4000ft"),
	("Climb to flight level two ninety", "Climb to FL290"),
	("Taxi to alpha thirteen", "Taxi to Alpha 13"),
	("Singapore 638 how do you read?", "SIA638 how do you read?"),

]


@pytest.mark.parametrize("input_transcription, expected_output", test_cases)
def test_apply_custom_fixes(input_transcription, expected_output, capsys):
	output = apply_custom_fixes(input_transcription)

	# Capture the standard output and print the results
	if output == expected_output:
		print(f"\nTest Passed!\nInput: '{input_transcription}'\nExpected: '{expected_output}'\nOutput: '{output}'")
	else:
		print(f"\nTest Failed!\nInput: '{input_transcription}'\nExpected: '{expected_output}'\nOutput: '{output}'")

	assert output == expected_output
