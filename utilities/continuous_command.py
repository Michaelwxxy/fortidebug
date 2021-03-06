#!/usr/bin/env python2.7

import os

# to be able to import our modules from the directory above
os.sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parsers.CurrentTime import ParserCurrentTime
from parsers.Processes import ParserProcesses
from _common import ssh, cycle, simple_command_with_timestamp, prepend_timestamp

import re
import sys

sshc, args = ssh([
	{ 'name':'--cycle-time',   'type':int, 'default':5,  'help':'How long should each cycle take' },
	{ 'name':'--command',      'required':True, 'action':'append', 'help':'What command to keep running, can repeat' },
	{ 'name':'--vdom',         'default':None, 'help':'VDOM to use when executing the command' },
	{ 'name':'--mgmt-vdom',    'default':False, 'action':'store_true',  'help':'Use management VDOM to execute the command' },
	{ 'name':'--grep',         'default':None, 'help':'Show only lines matching the regular expression' },
	{ 'name':'--directory-output', 'default':None, 'help':'Dump each command output as a separate file in a specified directory' },
	{ 'name':'--file-output',  'default':None, 'help':'Append the output to the specified file' },
], """
Execute specific command every `--cycle-time`. 

If there are VDOMs enabled on the device, then by default the command is execute in 'global' context,
but a specific VDOM can be used with `--vdom` option or `--mgmt-vdom` to use the management VDOM automatially.

The `--command` option can be repeated many times. If the context in some `--command` has to be different
than the context set globally with the other parameters, the command can start with '<...>' modifier.
The empty '<>' means to run it in management VDOM, '<global>' in global context and anything else
is used as the VDOM name.

Optionally you can use `--grep` option to only print the lines matching the regular expression.
""")

def do(sshc, commands, vdom, grep, output):
	etime = ParserCurrentTime(sshc).get()
	
	for command in commands:
		g = re.search('^<(.*?)>\s*(.*?)\s*$', command)
		if not g:
			this_vdom    = vdom
			this_command = command
		else:
			this_vdom    = g.group(1)
			this_command = g.group(2)
			if this_vdom.lower() == 'global': this_vdom = None

		out = sshc.clever_exec(this_command, this_vdom)
		if grep == None:
			print_output(sshc, out, etime, this_command, output)
		else:
			for line in out.split("\n"):
				if not grep.search(line): continue
				print_output(sshc, line, etime, this_command, output)
	
		sys.stdout.flush()
	
def print_output(sshc, txt, etime, command_name, output):
	if output['directory']:
		# If directory is specified, write the output per-file to the directory
		info = sshc.get_info()
		hostname = info['hostname']
		if info['hostname_extension'] != None: hostname += info['hostname_extension']
		hostname = re.sub('[^a-zA-Z0-9-]', ' ', hostname).strip().replace(' ', '_')
	
		fname = "%s/%s.%s.%s" % (output['directory'], hostname, command_name.replace(' ', '_'), etime.as_timestamp(),)
		with open(fname, "wb") as f:
			f.write(txt)
	
		print prepend_timestamp("Saved to %s" % (fname,), etime, command_name)

	elif output['file']:
		with open(output['file'], "ab") as f:
			f.write(txt)

		print prepend_timestamp("Appeneded to %s" % (output['file'],), etime, command_name)

	else:
		print prepend_timestamp(txt, etime, command_name)
		return
	

if __name__ == '__main__':
	#
	vdom = None

	if args.mgmt_vdom == True and args.vdom != None:
		print "Error: options '--vdom' and '--mgmt-vdom' are mutually exclusive"
		sys.exit(0)
	elif args.mgmt_vdom == True:
		vdom = ''
	elif args.vdom != None:
		vdom = args.vdom

	#
	grep = None
	if args.grep != None:
		grep = re.compile(args.grep)

	try:
		cycle(do, {
			'sshc': sshc, 
			'commands': args.command,
			'vdom': vdom,
			'grep': grep,
			'output': {
				'directory': args.directory_output,
				'file'     : args.file_output,
			},
		}, args.cycle_time, cycles_left=[args.max_cycles], debug=args.debug)
	except KeyboardInterrupt:
		sshc.destroy()

