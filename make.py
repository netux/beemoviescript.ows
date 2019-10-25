import re
import math
import os.path

from PyPDF2 import PdfFileReader
from PyPDF2.pdf import PageObject, ContentStream


def new_rule(index, actions):
	special_condition = '\n\t\tHas Spawned(Host Player) == True;' if index == 0 else ''
	actions_str = '\n\t\t'.join(actions)
	return f'rule("Script#{index+1}") {{\n\tevent {{\n\t\tOngoing - Global;\n\t}}\n\tconditions {{\n\t\tGlobal Variable(page) == {index};{special_condition}\n\t}}\n\tactions {{\n\t\t{actions_str}\n\t}}\n}}\n'

def new_text(text, index, color):
	return f'Create In-World Text(All Players(All Teams), Custom String("{text}", Null, Null, Null), Vector(18, {133-(index/2):.2f}, 100), 1.250, Do Not Clip, String, {color}, Default Visibility);'

def add_with_wraparound(actions, text, color):
	words = text.split(' ')
	next_text = ''
	while len(words) > 0:
		next_word = ' ' + words.pop(0)
		if len(next_text + next_word) > 125:
			next_text = next_text.strip()
			actions.append(new_text(next_text, len(actions), color))
			next_text = ''
		
		next_text += next_word
	
	next_text = next_text.strip()
	if len(next_text) > 0:
		actions.append(new_text(next_text, len(actions), color))

	return actions


parts = int(input('Parts (5):') or 5)

base_script = 'variables {\n\tglobal:\n\t\t0: page\n}\n'
if os.path.exists('./base.ows'):
	with open('./base.ows', 'r') as base_file:
		base_script = base_file.read()

with open('./script.pdf', 'rb') as pdf_file:
	pdf = PdfFileReader(pdf_file)
	pages_per_part = math.floor(pdf.getNumPages() / parts)

	rule_index = 0
	current_text = ''
	current_color = 'White'
	current_rule_actions = []
	overflowing = None
	is_on_speech_person_font = False

	for part in range(parts):
		script = base_script

		for i in range(1 + pages_per_part * part, pages_per_part * (part + 1)):
			page: PageObject = pdf.getPage(i)
			contentStream = ContentStream(page.getContents().getObject(), pdf)
			for operands, operator in contentStream.operations:
				if operator == b'Tf':
					is_on_speech_person_font = operands[0] == '/F1'
				elif operator == b'Tj':
					text = operands[0].strip()
					if text.strip() in ('', ':') or re.match(r'Page \d+/123', text):
						# is ignored
						continue
					elif re.match(r'^=*[A-Z0-9# ]+(?::|=+)$', text) or is_on_speech_person_font:
						# is speech person
						if len(current_rule_actions) != 0:
							current_rule_actions.append(None)

						text = re.sub(r'[^A-Z0-9# ]', '', text.upper())

						current_color = 'Lime Green'
						current_text = text + ':'
					elif text[0] in ('(', '['):
						# is annotation
						current_color = 'Yellow'

						if text[len(text)-1] in (')', ']'):
							current_text = text[1:len(text)-1]
						else:
							current_text = text[1:]
							overflowing = 'annotation'
					elif overflowing == 'annotation':
						if text[len(text)-1] in (')', ']'):
							current_text += ' ' + text[:len(text)-1]
							overflowing = None
						else:
							current_text += ' ' + text
					else:
						# is normal dialog
						current_text = text
						current_color = 'White'

					if overflowing == None:
						current_text = current_text.replace('"', '\\"')
						current_rule_actions = add_with_wraparound(current_rule_actions, current_text, current_color)

				while len(current_rule_actions) >= 30:
					excess = filter(lambda x: x is not None, current_rule_actions[30:])
					current_rule_actions = filter(lambda x: x is not None, current_rule_actions[0:30])
					script += new_rule(rule_index, current_rule_actions)
					current_rule_actions = list(excess)
					rule_index += 1
		
			script = script.replace('$page_count_human', str(rule_index + 1))
			script = script.replace('$page_count', str(rule_index))

		with open(f'script.{part}.ows', 'w') as output_file:
			output_file.write(script)
