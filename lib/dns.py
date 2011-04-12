import fabric.colors
import re
def manage_bind_record(zonefile_path, alias, hostname, mode="insert", testrun=False):
	if not zonefile_path :
		return None

	# open zone file
	modify = False
	start_search = False
	alias_exists = False
	new_zone_data = []
	zone_file = open( zone_file_path, "r")
	zone_data = zone_file.read()
	zone_file.close()

	cname_record = "".join([alias.ljust(40), "CNAME   ", target])
	search_marker = ";[==ldap-deploy aliases==]"

	for line in zone_data.splitlines() :
		if not start_search and (search_marker in line) :
			start_search = True

		if start_search :
			if alias in line :
				print( fabric.colors.yellow("CNAME DNS found : %s " % cname_record) )
				alias_exists = True

		if not alias_exists :
			new_zone_data.append(line)

	if alias_exists :
		if "remove" in mode :
			modify = True
		if "insert" in mode :
			modify = False
	else :
		if "remove" in mode :
			modify = False
		if "insert" in mode :
			modify = True
			print( fabric.colors.blue("Inserting new CNAME DNS record : %s " % cname_record ) )
			new_zone_data.append( cname_record )

	if not testrun and modify :
		new_zone_data = increment_serial(new_zone_data)
		zone_file = open( zone_file_path, "w")
		zone_file.write( "\n".join(new_zone_data) )
		zone_file.close()

def increment_serial( zone_data):
	rawstr = r"""(?P<serial>[\d]+)"""
	serial_number_regex = re.compile(rawstr)
	output = []
	# step through the lines.
	print( fabric.colors.blue("Looking for serial number ") )

	for line in zone_data :

		if "serial" in line :
			serial_match = serial_number_regex.search( line )
			if serial_match :
				#increment the serial number
				print( fabric.colors.blue("Serial Number found : %s " % line ) )
				serial = int(serial_match.group("serial"))
				if isinstance(serial, int) :
					new_serial = serial+1
					output.append( "{0} {1:<15} ; {2}".format( " "*23, new_serial , "serial number") )
					print( fabric.colors.yellow("Serial Increment Result : %s > %s" % (serial, serial+1) ) )
				else :
					output.append(line)
					print( fabric.colors.yellow("Could not Increment Serial : %s " % line ) )
		else :
			output.append(line)

	return output

