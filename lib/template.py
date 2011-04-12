import re, string

def template(source, context) :
	if isinstance(source, str) :
		if re.search('\$\{([a-zA-Z0-9_]+)\}', source)!=None :
			return string.Template( source ).safe_substitute( context )
		else :
			return source
	else :
		output = []
		for item in source :
			output.append( process_template( item ) )
	return output

def write_template(template_path, output_path, context):
	source_template = open(template_path)
	target_file = open(output_path, "w")
	target_file.write( template( source_template.read(), context) )
	target_file.close()
	source_template.close()

