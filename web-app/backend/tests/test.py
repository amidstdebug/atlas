def parse_number(text):
	units = {
		'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
		'six': 6, 'seven': 7, 'eight': 8, 'nine': 9
	}
	teens = {
		'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14,
		'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19
	}
	tens = {
		'twenty': 20, 'thirty': 30, 'forty': 40, 'fourty': 40, 'fifty': 50,
		'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90
	}
	scales = {'hundred': 100, 'thousand': 1000}
	words = text.lower().split()
	has_scales = any(word in scales for word in words)

	if has_scales:
		total = 0
		number_str = ''
		i = 0
		while i < len(words):
			word = words[i]
			if word in units:
				number_str += str(units[word])
				i += 1
			elif word in teens:
				number_str += str(teens[word])
				i += 1
			elif word in tens:
				if i + 1 < len(words) and words[i + 1] in units:
					number = tens[word] + units[words[i + 1]]
					number_str += str(number)
					i += 2
				else:
					number_str += str(tens[word])
					i += 1
			elif word in scales:
				scale = scales[word]
				if number_str == '':
					current = 1
				else:
					current = int(number_str)
				current *= scale
				total += current
				number_str = ''
				i += 1
			else:
				# Skip unrecognized words
				i += 1
		if number_str != '':
			total += int(number_str)
		return total
	else:
		# Build number by concatenating digits
		number_str = ''
		i = 0
		while i < len(words):
			word = words[i]
			if word in units:
				number_str += str(units[word])
				i += 1
			elif word in teens:
				number_str += str(teens[word])
				i += 1
			elif word in tens:
				if i + 1 < len(words) and words[i + 1] in units:
					number = tens[word] + units[words[i + 1]]
					number_str += str(number)
					i += 2
				else:
					number_str += str(tens[word])
					i += 1
			else:
				# Skip unrecognized words
				i += 1
		if number_str.lstrip('0') == '':
			# The number is zero or consists of leading zeros
			return 0
		elif number_str[0] == '0':
			# Preserve leading zeros
			return number_str
		else:
			return int(number_str)


# Test cases
print(parse_number("four thousand five hundred"))  # Output: 4500
print(parse_number("fourty five hundred"))  # Output: 4500
print(parse_number("four five zero zero"))  # Output: 4500
print(parse_number("fourty five zero zero"))  # Output: 4500
print(parse_number("four five hundred"))  # Output: 4500
print(parse_number("ten thousand five hundred"))  # Output: 10500
print(parse_number("ten thousand five twenty"))  # Output: 10520
print(parse_number("zero nine eight seven"))  # Output: '0987'
print(parse_number("one thousand"))