import common

import borg, importlib
importlib.import_module('.helpers', 'borg')

import os, gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

def selection_changed(selection, remove_button):
	remove_button.set_sensitive(selection.get_selected()[1] != None)

def remove_pattern(caller, selection):
	model, iterator = selection.get_selected()
	model.remove(iterator)

def add_path_dialog():
	return common.filechooser_dialog('Add path', Gtk.FileChooserAction.SELECT_FOLDER)

def path_msg_dialog(filename, row_filename):
	if filename == row_filename:
		msg_str = 'The selected path <tt>%s</tt> has already been added' % GLib.markup_escape_text(filename)
	else:
		msg_str = 'The path <tt>%s</tt> already includes the selected path [%s]' % (GLib.markup_escape_text(row_filename), filename)
	common.run_msg_dialog(Gtk.MessageType.INFO, msg_str)

class Patterns:

	def cell_edited(self, renderer, path, new_text):
		self.liststore.set_value(self.liststore.get_iter_from_string(path), 1, new_text)

	def add_path(self, caller):
		filename =  common.get_file(add_path_dialog())
		if filename:
			#check for duplicate
			for row in self.liststore:
				if row[0] == 0:
					row_filename = row[1]
					commonpath = os.path.commonpath((row_filename, filename))
					if commonpath == row_filename:
						path_msg_dialog(filename, row_filename)
						return
					elif commonpath == filename:
						self.liststore.remove(row.iter)
			self.liststore.append([0, filename])

	def add_pattern(self, caller, pattern_type):
		self.treeview.set_cursor(self.liststore.get_path(self.liststore.append([pattern_type, ''])),
		                                                 self.pattern_column, True)

	def add_pattern_file(self, caller):
		dialog = common.filechooser_dialog('Add pattern file', Gtk.FileChooserAction.OPEN)

		filename = common.get_file(dialog)
		if filename:
			filename = os.path.realpath(filename)
			#check for duplicate
			unique = True
			for row in self.liststore:
				if row[0] == 4 and row[1] == filename:
					common.run_msg_dialog(Gtk.MessageType.INFO, 'The pattern file <tt>%s</tt> has already been added' %
					                                            GLib.markup_escape_text(filename))
					return
			self.liststore.append([4, filename])

	def __init__(self):
		builder = Gtk.Builder.new_from_file('../data/ui/patterns.ui')

		self.grid = builder.get_object('grid')
		self.liststore = builder.get_object('liststore')
		self.treeview = builder.get_object('treeview')
		self.pattern_column = builder.get_object('pattern_column')
		self.remove_pattern_button = builder.get_object('remove_pattern_button')
		selection = builder.get_object('selection')
		pattern_cellrenderer = builder.get_object('pattern_cellrenderer')

		builder.get_object('type_column').set_cell_data_func(builder.get_object('type_cellrenderer'),
		                                                     lambda col, cell, model, iterator, data:
		                                                     cell.set_property('text',
		                                                     ['Path prefix', 'Fnmatch', 'Shell', 'Regex',
		                                                     'Pattern file']
		                                                     [model[iterator][0]]))
		builder.get_object('pattern_column').set_cell_data_func(pattern_cellrenderer,
		                                                        lambda col, cell, model, iterator, data:
		                                                        cell.set_property('editable', model[iterator][0] != 4))

		builder.connect_signals({'selection_changed' : (selection_changed, self.remove_pattern_button),
		                         'remove_pattern' : (remove_pattern, selection),
		                         'cell_edited' : self.cell_edited,
		                         'add_path' : self.add_path,
		                         'add_path_prefix' : (self.add_pattern, 0),
		                         'add_fnmatch_pattern' : (self.add_pattern, 1),
		                         'add_shell_pattern' : (self.add_pattern, 2),
		                         'add_regex_pattern' : (self.add_pattern, 3),
		                         'add_pattern_file' : self.add_pattern_file})

	def parse_patterns(self):
		result = []
		for row in self.liststore:
			row_type = row[0]
			if row_type == 0:
				result.append(borg.helpers.PathPrefixPattern(row[1]))
			elif row_type == 1:
				result.append(borg.helpers.FnmatchPattern(row[1]))
			elif row_type == 2:
				result.append(borg.helpers.ShellPattern(row[1]))
			elif row_type == 3:
				result.append(borg.helpers.RegexPattern(row[1]))
			else:
				file_path = row[1]
				try:
					patterns_file = open(file_path, 'r')
					result += borg.helpers.load_excludes(patterns_file)
					patterns_file.close()
				except OSError as e:
					common.run_msg_dialog(Gtk.MessageType.ERROR, 'Error occured while reading the file <tt>%s</tt>' %
					                                              GLib.markup_escape_text(file_path),
					                      '<tt>'+e.message()+'</tt>')
					return None
		return result
