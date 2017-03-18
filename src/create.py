import common, transitions, file_process, patterns, filetree, enums, process

import borg, importlib
importlib.import_module('.archive', 'borg')
importlib.import_module('.xattr', 'borg')
importlib.import_module('.archiver', 'borg')
importlib.import_module('.helpers', 'borg')
importlib.import_module('.repository', 'borg')
importlib.import_module('.compress', 'borg')

import multiprocessing, queue, os, time, stat, re, signal, gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject, Gio, GLib

def compression_set(caller):
	has_level = caller.get_active() > 1
	compression_level_label.set_sensitive(has_level)
	compression_level_spinbutton.set_sensitive(has_level)

def stop(caller, mp_queue):
	dialog = Gtk.MessageDialog(common.win, Gtk.DialogFlags.MODAL, Gtk.MessageType.WARNING, Gtk.ButtonsType.CANCEL,
	                           )
	dialog.add_button('_Stop', Gtk.ResponseType.ACCEPT)
	dialog.set_default_response(Gtk.ResponseType.CANCEL)

	if dialog.run() == Gtk.ResponseType.ACCEPT:
		GLib.source_remove(update_progress_source_id)
		subprocess.terminate()
		mp_queue.close()
		transitions.to_rep(Gtk.StackTransitionType.SLIDE_RIGHT)
		common.stop_button.hide()

	dialog.destroy()

def back_button_callback():
	def idle_func():
		common.reload_cur_repository()
		transitions.unload()
		transitions.to_rep()
	transitions.to_load()
	GLib.idle_add(idle_func)

def start(caller):
	global subprocess, iters, final_osize, update_progress_source_id
	name = name_entry.get_text()
	if name == '':
		common.set_error(name_entry)
		name_entry.empty_popover.show_all()
		return

	if checkpoint_re.match(name):
		common.set_error(name_entry)
		name_entry.checkpoint_popover.show_all()
		return

	for row in common.archive_liststore:
		if row[1] == name:
			common.set_error(name_entry)
			name_entry.exists_popover.show_all()
			return

	exclude_list = exclude_patterns.parse_patterns()
	if exclude_list != None:
		common.stack.set_visible_child_full('create', Gtk.StackTransitionType.SLIDE_LEFT)
		common.win.set_title('Creating archive')
		common.back_button.hide()
		common.stop_button.show()

		final_osize = None

		mp_queue = multiprocessing.Queue()

		common.stop_button.disconnect(common.stop_button_signal_id)
		common.stop_button_signal_id = common.stop_button.connect('clicked', stop, mp_queue)

		compression_selected = compression_combobox.get_active()
		if compression_selected == 0:
			common.cur_rep_key.compressor = borg.compress.CNONE()
		elif compression_selected == 1:
			common.cur_rep_key.compressor = borg.compress.LZ4()
		elif compression_selected == 2:
			common.cur_rep_key.compressor = borg.compress.ZLIB(compression_level_spinbutton.get_value_as_int())
		elif compression_selected == 3:
			common.cur_rep_key.compressor = borg.compress.LZMA(compression_level_spinbutton.get_value_as_int())

		common.cur_rep_cache.key.compressor = common.cur_rep_key.compressor

		process.write(filetree_obj,
		              multiprocessing.Process(target=file_process.create, name='borg-gtk-create',
		                                      args=(mp_queue, include_liststore, exclude_list, common.cur_path,
		                                            borg.xattr.buffer._thread_local.buffer,
		                                            common.get_archive(name, True)), daemon=True), mp_queue,
		              'Creating archive: {0}'.format(name), back_button_callback,
		              'You will resume the backup from the last made checkpoint.\n'
	                  'Are you sure you want to stop creating this archive?')

def preview(caller):
	global preview_not_setup
	if preview_not_setup:
		global preview_filetree_obj
		preview_filetree_obj = filetree.FileTree(False)
		preview_filetree_obj.grid.set_border_width(5)

		common.stack.add_named(preview_filetree_obj.grid, 'preview')

		preview_not_setup = False
	exclude_list = exclude_patterns.parse_patterns()
	if exclude_list != None:
		global preview_source_id
		mp_queue = multiprocessing.Queue()
		preview_process = multiprocessing.Process(target=file_process.preview, name='borg-gtk-preview',
		                                          args=(mp_queue, include_liststore, exclude_list, common.cur_path))
		process.read(preview_filetree_obj, preview_process, mp_queue, 'preview', 'Create preview',
		             lambda: transitions.to_create_form(None, Gtk.StackTransitionType.SLIDE_RIGHT))

def add_path(caller):
	filename = common.get_file(patterns.add_path_dialog())
	if filename:
		#check for duplicate
		for row in include_liststore:
			row_filename = row[0]
			commonprfx = os.path.commonprefix((row_filename, filename))
			if commonprfx == row_filename:
				patterns.path_msg_dialog(filename, row_filename)
				return
			elif commonprfx == filename:
				include_liststore.remove(row.iter)

		include_liststore.append([filename])

def setup(caller):
	global name_entry, exclude_patterns, compression_combobox, compression_level_label, remove_button
	global compression_level_spinbutton, checkpoint_re, include_liststore, preview_not_setup, filetree_obj

	checkpoint_re = re.compile(r'.*\.checkpoint(\.[0-9]+)?')

	builder = Gtk.Builder.new_from_file('../data/ui/create.ui')

	common.stack.add_named(builder.get_object('form_grid'), 'create_form')

	name_entry = builder.get_object('name_entry')
	name_entry.empty_popover = common.error_popover(name_entry, 'A name is required', Gtk.PositionType.TOP)
	name_entry.checkpoint_popover = common.error_popover(name_entry, "The '.checkpoint' and '.checkpoint.N' phrases are not allowed",
	                                                     Gtk.PositionType.TOP)
	name_entry.exists_popover = common.error_popover(name_entry, 'This archive already exists', Gtk.PositionType.TOP)

	exclude_patterns = patterns.Patterns()

	patterns_grid = builder.get_object('patterns_grid')
	patterns_grid.attach(exclude_patterns.grid, 0,4,1,1)

	compression_combobox = builder.get_object('compression_combobox')

	compression_level_label = builder.get_object('compression_level_label')
	compression_level_spinbutton = builder.get_object('compression_level_spinbutton')

	include_liststore = builder.get_object('include_liststore')
	path_selection = builder.get_object('path_selection')
	remove_button = builder.get_object('remove_button')

	filetree_obj = filetree.FileTree(True)
	process.write_add_tree(filetree_obj)

	preview_not_setup = True

	builder.connect_signals({'block_slash': common.block_slash,
	                         'compression_set': compression_set,
	                         'start': start,
	                         'preview': preview,
	                         'add_path' : add_path,
	                         'selection_changed' : (patterns.selection_changed, remove_button),
	                         'remove_path' : (patterns.remove_pattern, path_selection)})

	caller.disconnect(button_signal_id)
	caller.connect('clicked', transitions.to_create_form)

	transitions.to_create_form(caller)
