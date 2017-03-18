import common, enums

import borg, importlib
importlib.import_module('.archiver', 'borg')
importlib.import_module('.helpers', 'borg')

import multiprocessing, queue, gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

def remove_source():
	GLib.source_remove(update_source_id)

def back_button_callback(caller, process, mp_queue, tree, transition):
	process.terminate()
	mp_queue.close()
	tree.model.clear()
	transition()

def read_update(mp_queue, tree):
	global update_source_id, remove_source_signal_id
	try:
		report = mp_queue.get_nowait()
	except queue.Empty:
		pass
	else:
		if report[0] == enums.ALL_ADDED:
			common.back_button.disconnect(remove_source_signal_id)
			mp_queue.close()
			return GLib.SOURCE_REMOVE
		tree.append(*report[1:])

	return GLib.SOURCE_CONTINUE

# reading operations such as previewing and listing archives
def read(tree, process, mp_queue, stack_name, win_title, back_transition):
	global update_source_id, remove_source_signal_id
	update_source_id = GLib.idle_add(read_update, mp_queue, tree, priority=GLib.PRIORITY_LOW)
	process.start()

	common.stack.set_visible_child_full(stack_name, Gtk.StackTransitionType.SLIDE_LEFT)
	common.win.set_title(win_title)
	common.back_button.disconnect(common.back_button_signal_id)

	remove_source_signal_id = common.connect_back_button_one_time(remove_source)
	common.back_button_signal_id = common.back_button.connect('clicked', back_button_callback, process, mp_queue, tree,
	                                                          back_transition)

def write_update(mp_queue, tree):
	global n_files, total_size, all_added, remove_source_signal_id
	try:
		report = mp_queue.get_nowait()
	except queue.Empty:
		pass
	else:
		report_status = report[0]
		if report_status == enums.ADDED:
			tree.append(*report[1:])
			n_files += 1
			total_size += report[3]
		elif report_status == enums.PROCESSING:
			tree.set_processing_status_treepath(report[1])
			status_label.set_markup('<i>Backing up <tt>{0}</tt></i>'.format(GLib.markup_escape_text(report[2])))
			if not all_added:
				progressbar.pulse()
		elif report_status == enums.DONE:
			tree.set_done_status_treepath(report[1])
		elif report_status == enums.ALL_ADDED:
			all_added = True
		elif report_status == enums.STATS_UPDATE:
			size_processed, csize_processed, usize_processed, n_files_processed = report[1:]
			original_size_label.set_text('{0} / {1}'.format(borg.helpers.format_file_size(size_processed),
			                                                borg.helpers.format_file_size(total_size)))
			compressed_size_label.set_text(borg.helpers.format_file_size(csize_processed))
			deduplicated_size_label.set_text(borg.helpers.format_file_size(usize_processed))
			n_files_label.set_text('{0} / {1}'.format(n_files_processed, n_files))
			if all_added:
				progressbar.set_fraction(float(size_processed)/total_size)
		elif report_status == enums.COMPLETE:
			status_label.set_markup('<b>Done!</b>')
			common.stop_button.hide()
			common.stop_button.disconnect(stop_button_signal_id)
			common.back_button.disconnect(remove_source_signal_id)
			common.back_button.show()
			return GLib.SOURCE_REMOVE
		else:
			# error
			tree.set_error_status_treepath(report[1])
			msg = '%s: %s'
			warning_textbuffer.insert(warning.textbuffer.get_end_iter(), msg)
			borg.archiver.logger.warning(msg)

	return GLib.SOURCE_CONTINUE

write_not_setup = True

def write_add_tree(tree):
	global write_not_setup
	if write_not_setup:
		global process_grid, progressbar, status_label, original_size_label, compressed_size_label
		global deduplicated_size_label, n_files_label, warning_textbuffer
		builder = Gtk.Builder.new_from_file('../data/ui/process.ui')
		process_grid = builder.get_object('grid')
		common.stack.add_named(process_grid, 'process')
		progressbar = builder.get_object('progressbar')
		status_label = builder.get_object('status_label')
		original_size_label = builder.get_object('original_size_label')
		compressed_size_label = builder.get_object('compressed_size_label')
		deduplicated_size_label = builder.get_object('deduplicated_size_label')
		n_files_label = builder.get_object('n_files_label')
		warning_textview = builder.get_object('warning_textview')
		warning_textbuffer = warning_textview.get_buffer()
		write_not_setup = False

	process_grid.attach(tree.grid, 0, 8, 2, 1)
	tree.grid.hide()

def stop_response(dailog, repsonse_id):
	if response_id == Gtk.ResponseType.ACCEPT:
		common.back_button.emit('clicked')
		common.stop_button.hide()
	dialog.destroy()

def stop(caller, stop_message):
	dialog = Gtk.MessageDialog(common.win, Gtk.DialogFlags.MODAL, Gtk.MessageType.WARNING, Gtk.ButtonsType.CANCEL,
	                           stop_message)
	dialog.add_button('_Stop', Gtk.ResponseType.ACCEPT)
	dialog.set_default_response(Gtk.ResponseType.CANCEL)

	dialog.connect('response', stop_response)

# writing operations such as creating and extracting archives
def write(tree, process, mp_queue, win_title, back_transition, stop_message):
	global update_source_id, remove_source_signal_id, stop_button_signal_id, n_files, total_size, all_added
	n_files = 0
	total_size = 0
	all_added = False

	tree.grid.show_all()

	update_source_id = GLib.idle_add(write_update, mp_queue, tree, priority=GLib.PRIORITY_LOW)
	process.start()

	common.stack.set_visible_child_full('process', Gtk.StackTransitionType.SLIDE_LEFT)
	common.stop_button.show()
	common.back_button.hide()
	stop_button_signal_id = common.stop_button.connect('clicked', stop, mp_queue, stop_message)
	common.win.set_title(win_title)
	common.back_button.disconnect(common.back_button_signal_id)

	remove_source_signal_id = common.connect_back_button_one_time(remove_source)
	hide_tree_signal_id = common.connect_back_button_one_time(lambda: tree.grid.hide())
	common.back_button_signal_id = common.back_button.connect('clicked', back_button_callback, process, mp_queue, tree,
	                                                          back_transition)
