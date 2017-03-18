import common

import os
import json
import locale
import datetime
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio

def simplest_path(path):
	home = os.path.expanduser('~')
	#if it's in the home directory, then
	if os.path.commonpath((path, home)) == home:
		return os.path.relpath(path, home)
	else:
		return path

def refresh():
	global listbox, config_file, config_data
	#clear the list
	listbox.foreach(lambda child, data: child.destroy(), None)
	del common.config_data

	common.config_file.seek(0)
	file_contents = common.config_file.read()
	if file_contents == '':
		common.config_data = {}
	else:
		common.config_data = json.loads(file_contents)

		locale_date_format = locale.nl_langinfo(locale.D_FMT)
		day_before_month = locale_date_format.find('%d') < locale_date_format.find('%m')

		for path in common.config_data:
			row = Gtk.ListBoxRow()
			row.path = path
			row.time = common.config_data[path]['atime']

			grid = Gtk.Grid()
			grid.set_border_width(5)
			grid.set_row_spacing(10)

			spl = os.path.split(path)

			name_label = Gtk.Label()
			name_label.set_markup('<big><b>'+spl[1]+'</b></big>')
			name_label.set_halign(Gtk.Align.START)
			name_label.set_hexpand(True)
			grid.attach(name_label, 0,0,1,1)

			path_label = Gtk.Label(simplest_path(spl[0]))
			path_label.set_halign(Gtk.Align.START)
			path_label.get_style_context().add_class(Gtk.STYLE_CLASS_DIM_LABEL)
			grid.attach(path_label, 0,1,2,1)

			datetime_obj = datetime.datetime.fromtimestamp(row.time)
			time_label = Gtk.Label()
			if day_before_month:
				time_label.set_text(datetime_obj.strftime('%-d %B'))
			else:
				time_label.set_text(datetime_obj.strftime('%B %-d'))
			time_label.set_halign(Gtk.Align.END)
			time_label.get_style_context().add_class(Gtk.STYLE_CLASS_DIM_LABEL)
			grid.attach(time_label, 1,0,1,1)

			row.add(grid)
			row.show_all()
			listbox.prepend(row)

def stack_transition(transition):
	if common.config_data:
		page_name = 'list'
	else:
		page_name = 'empty'
	common.stack.set_visible_child_full(page_name, transition)
