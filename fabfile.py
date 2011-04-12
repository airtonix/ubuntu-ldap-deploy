#!/usr/bin/python
import os, re, string
import random
import tempfile

import lib.dns
import lib.files
import lib.template

import fabric.api
import fabric.operations
import fabric.contrib.console
import fabric.colors


#======================
# Tools
#

def _kwarg(context, key):
	if key in context.keys():
		return context[key]
	else:
		return ""


def password(length=8, chars=string.letters + string.digits, console=True):
	output = ''.join([random.choice(chars) for i in xrange(length)])
	if console :
		print( output )
	else :
		return output



fabric.api.env.HEREPATH = os.path.abspath( os.path.dirname(__file__) )
fabric.api.env.HOSTNAME = fabric.operations.local("hostname", capture=True )
fabric.api.env.DOMAIN = None
fabric.api.env.ROOTPASSWORD = None
fabric.api.env.ADMINPASSWORD = None
fabric.api.env.TMP_WORKSPACE_ROOT = tempfile.mkdtemp()
fabric.api.env.DN = None
## Create Temporary Build Directory
lib.files.makedir( fabric.api.env.TMP_WORKSPACE_ROOT )

#======================
# Fabrics
#
def install():
	if fabric.contrib.console.confirm( "\t" + fabric.colors.yellow("Install LDAP daemon?") ) :
		fabric.operations.local("sudo apt-get install slapd ldap-utils")

def purge():
	"""
		Purge the ldap settings and database
		  removes :
		    /etc/ldap/*
		    /var/lib/ldap/*
	"""
	message_prefix = fabric.colors.cyan("openLDAP Package Management") + "["+ fabric.colors.red("PURGE") +"] : "
	question = fabric.colors.yellow("Purge openLDAP Config and Database?")
	if fabric.contrib.console.confirm( question ) :
		fabric.operations.local("sudo service slapd stop")
		fabric.operations.local("sudo apt-get purge slapd ldap-utils")

def reset():
	"""
		Purge the ldap settings and database
		Then recreate new default files.
		  Removes :
		    /etc/ldap/*
		    /var/lib/ldap/*
		  Runs :
		  	dpkg-reconfigure slapd
	"""
	message_prefix = fabric.colors.cyan("openLDAP Config") + "["+ fabric.colors.red("RESET") +"] : "
	question = fabric.colors.yellow("Reset openLDAP Config and Database?")
	if fabric.contrib.console.confirm( question ) :
		fabric.operations.local("sudo rm /etc/ldap -rf")
		fabric.operations.local("sudo rm /var/lib/ldap -rf")
		fabric.operations.local("sudo dpkg-reconfigure slapd")

def _variables():
	"""
		Sets some required variables
	"""
	fabric.contrib.console.prompt( text=fabric.colors.blue("ROOT Password : "), key="ROOTPASSWD", default=password( 16, console=False) )
	fabric.contrib.console.prompt( text=fabric.colors.blue("LDAP Admin Password : "), key="ADMINPASSWD", default=password( 16, console=False ) )
	fabric.contrib.console.prompt( text=fabric.colors.blue("Network Domain Name : "), key="DOMAIN" )
	fabric.api.env.DN="dc={0},dc={1}".format(fabric.api.env.HOSTNAME, fabric.api.env.DOMAIN)


def dns(create=False):
	"""
		Defaults to reporting current situation.
		This makes it hard for console users to directly stuff up
	"""
	message_prefix = fabric.colors.cyan("Bind9 DNS CNAME Alias Records") +" : "
	if create :
		print( message_prefix + fabric.colors.red("This process assumes you already have a working bind9 installation.") )
		if fabric.contrib.console.confirm( "\t" + fabric.colors.yellow("Create Bind DNS Cname Records") ) :

			if not fabric.api.env.DOMAIN or not fabric.api.env.HOSTNAME :
				setup()

			zonefile_path = fabric.contrib.console.prompt("Path to the Zone File", default="/etc/bind/zones/{0}.db".format(fabric.api.env.DOMAIN) )
			print( message_prefix + fabric.colors.yellow("Inserting CNAME Alias") )
			append(zonefile_path, dns_template("ldap") )
			append(zonefile_path, dns_template("ldap-master") )
	else :
		print( message_prefix + fabric.colors.cyan("TODO: Print Current BIND9 DNS Records") )

#================
# SCHEMAS
#
def default_schema():
	message_prefix = fabric.colors.cyan("Default Schema") +" : "

	if fabric.contrib.console.confirm( "\t" + fabric.colors.yellow("Insert Default LDIF Schemas") ) :
		fabric.operations.local("sudo ldapadd -Y EXTERNAL -H ldapi:/// -f /etc/ldap/schema/cosine.ldif")
		fabric.operations.local("sudo ldapadd -Y EXTERNAL -H ldapi:/// -f /etc/ldap/schema/nis.ldif")
		fabric.operations.local("sudo ldapadd -Y EXTERNAL -H ldapi:/// -f /etc/ldap/schema/inetorgperson.ldif")

def frontend_schema():
	message_prefix = fabric.colors.cyan("Frontend Schema") +" : "

	if fabric.contrib.console.confirm( "\t" + fabric.colors.yellow("Insert Default Frontend LDIF Schemas") ) :

		lib.files.makedir( os.path.join(fabric.api.env.TMP_WORKSPACE_ROOT, "schemas") )
		frontend_template_path = os.path.join(fabric.api.env.HEREPATH, "schemas", "frontend.ldif")
		frontend_path = os.path.join(fabric.api.env.TMP_WORKSPACE_ROOT, "schemas", "frontend.ldif")

		fabric.contrib.console.prompt(
			fabric.colors.yellow("LDAP Root Password"),
			key = "ROOTPASSWORD",
			default = password(16, console=True)
		)

		print( message_prefix + fabric.colors.yellow("Processing Schema {0}".format(frontend_path)) )
		write_template( frontend_template_path, frontend_path, env )

		print( message_prefix + fabric.colors.yellow("Inserting schema {0}".format(frontend_path)) )
		fabric.operations.local("sudo ldapadd -Y EXTERNAL -H ldapi:/// -f {0}".format( frontend_path ) )

def backend_schema():
	message_prefix = fabric.colors.cyan("Backend Schema") +" : "

	if fabric.contrib.console.confirm( "\t" + fabric.colors.yellow("Insert Default Backend LDIF Schemas") ) :

		lib.files.makedir( os.path.join(fabric.api.env.TMP_WORKSPACE_ROOT, "schemas") )
		backend_template_path = os.path.join(fabric.api.env.HEREPATH, "schemas", "backend.ldif")
		backend_path = os.path.join(fabric.api.env.TMP_WORKSPACE_ROOT, "schemas", "backend.ldif")

		print( message_prefix + fabric.colors.yellow("Processing Schema {0}".format(backend_path)) )
		write_template( backend_template_path, backend_path, env )

		print( message_prefix + fabric.colors.yellow("Inserting schema {0}".format(backend_path)) )
		fabric.operations.local("sudo ldapadd -Y EXTERNAL -H ldapi:/// -f {0}".format( backend_path ) )


#=================
# Group LDIFs
#
def group():
	message_prefix = fabric.colors.cyan("Preseed Group") +" : "

	lib.files.makedir( os.path.join(fabric.api.env.TMP_WORKSPACE_ROOT, "schemas", "groups") )
	group_template_path = os.path.join(fabric.api.env.HEREPATH, "schemas", "groups", "template.ldif")

	context = {
		"GROUPNAME" : fabric.contrib.console.prompt( message_prefix + fabric.colors.yellow("Groupname : ") ),
		"GROUPID" : fabric.contrib.console.prompt( message_prefix + fabric.colors.yellow("Unix GroupID : ") ),
		"DN" : fabric.contrib.console.prompt( message_prefix + fabric.colors.yellow("Distinguished Name : "), default=fabric.api.env.DN),
	}

def _groups():
	message_prefix = fabric.colors.cyan("Preseed Groups") +" : "
	if fabric.contrib.console.confirm( "\t" + fabric.colors.yellow("Insert Preseeded Groups?") ) :
		group()
		while fabric.contrib.console.confirm( fabric.colors.yellow("Create another groups ") ) :
			group()


#=================
# User LDIFs
#
def person(*args, **kwargs):
	lib.files.makedir( os.path.join(fabric.api.env.TMP_WORKSPACE_ROOT, "schemas", "users") )
	message_prefix = fabric.colors.cyan("Person Record") +" : "
	context = kwargs

	if not fabric.api.env.DN :
		setup()

	if "password" in kwargs.keys():
		pword = kwarg(context, 'password')
	else:
		pword = password( 16, console=False)

	context = {
		"USERNAME" : fabric.contrib.console.prompt( message_prefix + fabric.colors.yellow("Username : "), default=_kwarg(context, 'username') ),
		"FIRSTNAME" : fabric.contrib.console.prompt( message_prefix + fabric.colors.yellow("Firstname : "), default=_kwarg(context, 'firstname') ),
		"LASTNAME" : fabric.contrib.console.prompt( message_prefix + fabric.colors.yellow("Lastname : "), default=_kwarg(context, 'lastname') ),
		"INITIALS" : fabric.contrib.console.prompt( message_prefix + fabric.colors.yellow("Initials : "), default=_kwarg(context, 'initials') ),
		"TITLE" : fabric.contrib.console.prompt( message_prefix + fabric.colors.yellow("Title : "), default=_kwarg(context, 'title') ),
		"USERID" : fabric.contrib.console.prompt( message_prefix + fabric.colors.yellow("unix User ID : "), default=_kwarg(context, 'uid') ),
		"GROUPID" : fabric.contrib.console.prompt( message_prefix + fabric.colors.yellow("unix Group ID : "), default=_kwarg(context, 'gid') ),
		"USERPASSWORD" : fabric.contrib.console.prompt( message_prefix + fabric.colors.yellow("User Password : "), default=pword ),
		"PHONEMOBILE" : fabric.contrib.console.prompt( message_prefix + fabric.colors.yellow("Mobile Phone : "), default=_kwarg(context, 'mobile') ),
		"PHONEHOME" : fabric.contrib.console.prompt( message_prefix + fabric.colors.yellow("Home Phone : "), default=_kwarg(context, 'phone') ),
		"ORGANISATION" : fabric.contrib.console.prompt( message_prefix + fabric.colors.yellow("Organisation : "), default=_kwarg(context, 'organisation') ),
		"POSTALADDRESS" : fabric.contrib.console.prompt( message_prefix + fabric.colors.yellow("Address : "), default=_kwarg(context, 'address') ),
		"POSTCODE" : fabric.contrib.console.prompt( message_prefix + fabric.colors.yellow("Postcode : "), default=_kwarg(context, 'postcode') ),
		"SUBURB" : fabric.contrib.console.prompt( message_prefix + fabric.colors.yellow("Suburb : "), default=_kwarg(context, 'suburb') ),
		"DN" : fabric.contrib.console.prompt( message_prefix + fabric.colors.yellow("DN : "), default=fabric.api.env.DN ),
		"DOMAIN" : fabric.contrib.console.prompt( message_prefix + fabric.colors.yellow("DOMAIN : "), default=fabric.api.env.DOMAIN ),
		"HOSTNAME" : fabric.contrib.console.prompt( message_prefix + fabric.colors.yellow("HOSTNAME : "), default=fabric.api.env.HOSTNAME ),
	}

	person_template_path = os.path.join(fabric.api.env.HEREPATH, "schemas", "users", "person.ldif")
	person_ldif_path = os.path.join(fabric.api.env.TMP_WORKSPACE_ROOT, "schemas", "users", "{0}.ldif".format( context["USERNAME"] ) )

	print( message_prefix + yellow("Creating Temporary User LDIF") )
	write_template( person_template_path, person_ldif_path, context )
	fabric.operations.local("sudo ldapadd -Y EXTERNAL -H ldapi:/// -f {0}".format( person_ldif_path ) )

def admin_user():
	lib.files.makedir( os.path.join(fabric.api.env.TMP_WORKSPACE_ROOT, "schemas", "users") )
	user_template_path = os.path.join(fabric.api.env.HEREPATH, "schemas", "users", "admin.ldif")

	print( message_prefix + fabric.colors.yellow("Inserting LDAP Admin") )
	user_path = os.path.join(fabric.api.env.TMP_WORKSPACE_ROOT, "schemas", "users", "admin.ldif")
	context = {
		"ADMINPASSWORD" : fabric.contrib.console.prompt( fabric.colors.yellow("LDAP Administrator Password"), key="ADMINPASSWORD", default=password(16, console=True) ),
		"HOSTNAME" : fabric.api.env.HOSTNAME,
		"DOMAIN" : fabric.api.env.DOMAIN
	}
	write_template( user_template_path, user_path, context )




def _inputseed( name = None ):
	if not name :
		return None

	message_prefix = fabric.colors.cyan( name.capitalize() ) +" : "
	temp_dir = os.path.join(fabric.api.env.TMP_WORKSPACE_ROOT, "schemas", name )
	question = fabric.colors.yellow( "Manually input LDIF Preseed {0} Data?".format(name.capitalize()) )
	lib.files.makedir( temp_dir )

	while fabric.contrib.console.confirm( question ) :
		if name == "groups":
			group()
		if name == "users":
			user( )

def inputseed( name=None ):
	if not name or not name =="users" or not name == "groups" :
		return None
	else :
		_inputseed( name = name )


def _preseed( name = None):

	if name == "groups" or name == "users":
		message_prefix = fabric.colors.cyan( name.capitalize() ) + " : "
		question = fabric.colors.yellow( "Scan for LDIF Preseed {0} Data?".format(name.capitalize()) )
		tmp_dir = os.path.join( fabric.api.env.TMP_WORKSPACE_ROOT, "schemas", name )
		preseed_source = os.path.join(fabric.api.env.HEREPATH, "preseed", name )

		if fabric.contrib.console.confirm( question ) :
			lib.files.makedir( tmp_dir )
			if os.path.exists( preseed_source ):

				for ldif in os.listdir( preseed_source ) :
					if ldif.endswith(".ldif"):
						ldif_path = os.path.join(preseed_source, ldif)
						if name == "groups":
							group( preseed = ldif_path )
						if name == "users":
							user( preseed = ldif_path )

def preseed( name = None ):

	if name == "groups" or name == "users":
		_preseed( name )
	else :
		return None

def start():
	_variables()
	# Create DNS Records
	dns(create=True)
	# Install SLAPD
	install()
	# default schema
	default_schema()
	# backend schema
	backend_schema()
	# frontend schema
	frontend_schema()
	#
	preseed(name="groups")
#	inputseed(name = "groups")
#	#
	preseed(name="users")
#	inputseed(name = "users")

