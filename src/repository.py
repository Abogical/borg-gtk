import common, replist, transitions, create, filetree, list_process, process

import borg, importlib
importlib.import_module('.helpers', 'borg')
importlib.import_module('.key', 'borg')

import binascii, multiprocessing, queue, re, json, warnings, os, time, gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, GLib, GObject

not_setup = True

def archive_selected(selection):
	global select_grid
	model, iterator = selection.get_selected()
	if iterator:
		global stack
		archive_name = model[iterator][1]

		def set_info_labels():
			obj = model[iterator][2]

			builder.get_object('fingerprint').set_markup('<small>'+obj.fingerprint+'</small>')

			for key, value in obj.info.items():
				builder.get_object(key).set_text(value)

			for key, value in model.all_info.items():
				builder.get_object(key).set_text(value)

			select_name_label.set_markup('<big><b>'+archive_name+'</b></big>')

		if model[iterator][2]:
			set_info_labels()
		else:
			transitions.to_load()

			def idle_func():
				new_obj = GObject.Object()
				new_obj.archive = common.get_archive(archive_name, False)
				stats = new_obj.archive.calc_stats(common.cur_rep_cache)
				new_obj.fingerprint = binascii.hexlify(new_obj.archive.id).decode('ascii')
				new_obj.info = {'hostname' : new_obj.archive.metadata[b'hostname'],
				                'username' : new_obj.archive.metadata[b'username'],
				                'time_start' : borg.helpers.format_time(borg.helpers.to_localtime(new_obj.archive.ts)),
				                'time_end' : borg.helpers.format_time(borg.helpers.to_localtime(new_obj.archive.ts_end)),
				                'command' : ' '.join(new_obj.archive.metadata[b'cmdline']),
				                'n_files' : str(stats.nfiles),
				                'original_size' : stats.osize_fmt,
				                'compressed_size' : stats.csize_fmt,
				                'deduplicated_size' : stats.usize_fmt}
				model[iterator][2] = new_obj

				if not hasattr(model, 'all_info'):
					summary = common.cur_rep_cache.chunks.summarize()
					model.all_info = {'all_original_size' : borg.helpers.format_file_size(summary[0]),
					                  'all_compressed_size' : borg.helpers.format_file_size(summary[1]),
					                  'all_deduplicated_size' : borg.helpers.format_file_size(summary[3]),
					                  'unique_chunks' : str(summary[4]),
					                  'total_chunks' : str(summary[5])}

				set_info_labels()

				select_grid.show_all()
				transitions.unload()

			GLib.idle_add(idle_func)
	else:
		select_grid.hide()

list_not_setup = True
def archive_list(model, iterator):
	global list_not_setup, list_update_source_id
	if list_not_setup:
		global list_archivetree_obj

		list_archivetree_obj = filetree.ArchiveTree(False)
		list_archivetree_obj.grid.set_border_width(5)

		common.stack.add_named(list_archivetree_obj.grid, 'archive_list')

		list_not_setup = False

	archive = model[iterator][2].archive
	mp_queue = multiprocessing.Queue()
	process.read(list_archivetree_obj,
	             multiprocessing.Process(target=list_process.list, name='borg-gtk-list', args=(mp_queue, archive)),
	             mp_queue, 'archive_list', 'Archive: {0}'.format(archive.name),
	             lambda: transitions.to_rep(Gtk.StackTransitionType.SLIDE_RIGHT))

def archive_extract(caller):
	model, iterator = selection.get_selected()
	if iterator:
		pass

# this needs to be improved
def archive_delete(model, iterator):
	archive = model[iterator][2].archive

	dialog = Gtk.MessageDialog(common.win, Gtk.DialogFlags.MODAL, Gtk.MessageType.WARNING, Gtk.ButtonsType.CANCEL,
	                           'Are you sure you want to delete the archive <b>%s</b>?' % GLib.markup_escape_text(archive.name))

	dialog.set_property('use-markup', True)
	dialog.add_button('_Delete', Gtk.ResponseType.ACCEPT)
	dialog.set_default_response(Gtk.ResponseType.CANCEL)

	accepted = dialog.run() == Gtk.ResponseType.ACCEPT

	dialog.destroy()

	if accepted:
		transitions.to_load()
		dialog = Gtk.MessageDialog(common.win, Gtk.DialogFlags.MODAL, Gtk.MessageType.INFO, Gtk.ButtonsType.NONE,
		                           '<i>Deleting</i>')
		dialog.set_property('use-markup', True)
		dialog.show_all()
		def idle_func():
			archive.delete(borg.helpers.Statistics())
			common.cur_rep_manifest.write()
			common.cur_repository.commit()
			common.cur_rep_cache.commit()
			model.remove(iterator)
			dialog.hide()
			transitions.unload()
		GLib.idle_add(idle_func)

def get_selected_callback(caller, func):
	model, iterator = selection.get_selected()
	if iterator:
		func(model, iterator)

def start():
	global not_setup
	if not_setup:
		global builder, select_grid, select_name_label, selection

		builder = Gtk.Builder.new_from_file('../data/ui/repository.ui')

		grid = builder.get_object('grid')
		common.stack.add_named(grid, 'rep')

		common.archive_liststore = builder.get_object('liststore')
		create.button_signal_id = builder.get_object('create_button').connect('clicked', create.setup)

		select_grid = builder.get_object('select_grid')

		select_name_label = builder.get_object('select_name_label')

		selection = builder.get_object('selection')

		builder.connect_signals({'archive_selected' : archive_selected,
		                         'archive_delete' : (get_selected_callback, archive_delete),
		                         'archive_list' : (get_selected_callback, archive_list)})

		not_setup = False

	common.fill_archive_liststore()

	#add path to config file with time
	common.config_data[common.cur_path] = {'atime': time.time()}
	common.config_file.seek(0)
	common.config_file.truncate()
	json.dump(common.config_data, common.config_file)
	replist.refresh()

	transitions.unload()
	transitions.to_rep()

pass_not_setup = True
pass_again = False

def set_pass(passphrase):
	os.environ['BORG_PASSPHRASE'] = passphrase

def start_with_path(path):
	transitions.to_load()
	def idle_func():
		common.cur_path = path
		try:
			common.prepare()
			#Get repository, cache and manifest and lock them
			common.set_cur_repository(common.cur_path, False)
			start()
		except borg.key.PassphraseWrong as e:
			common.unset_cur_repository(e)
			transitions.unload()
			global pass_not_setup, pass_again, msg_label, pass_entry
			if pass_not_setup:
				builder = Gtk.Builder.new_from_file('../data/ui/passphrase.ui')

				grid = builder.get_object('grid')
				common.stack.add_named(grid, 'pass')

				msg_label = builder.get_object('msg_label')

				pass_entry = builder.get_object('entry')

				button = builder.get_object('button')
				def enter_pass(caller):
					set_pass(pass_entry.get_text())
					transitions.to_load()
					GLib.idle_add(idle_func)

				builder.connect_signals({'click_button' : lambda caller: button.clicked(),
				                         'enter_pass' : enter_pass})

				pass_not_setup = False

			common.stack.set_visible_child_full('pass', Gtk.StackTransitionType.CROSSFADE)
			common.addrep_button.hide()
			common.back_button.show()
			common.win.set_title('Passphrase')
			common.back_button.disconnect(common.back_button_signal_id)
			def callback(caller):
				pass_again = False
				transitions.to_replist()
			common.back_button_signal_id = common.back_button.connect('clicked', callback)
			if pass_again:
				msg_label.set_text('Passphrase Incorrect. Try again')
			else:
				msg_label.set_text('Passphrase needed to read or modify the contents of this repository')
			pass_again = True

	GLib.idle_add(idle_func)
