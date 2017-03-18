import common, repository, transitions

import borg
import importlib
importlib.import_module('.archiver', 'borg')
importlib.import_module('.repository', 'borg')
importlib.import_module('.key', 'borg')
importlib.import_module('.helpers', 'borg')
importlib.import_module('.cache', 'borg')

import argparse
import os
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gio

def reset_error():
	common.remove_error(directory_name_entry)
	common.remove_error(directory_path_button)
	common.remove_error(encryption_passphrase_entry)
	common.remove_error(encryption_passphrase_again_entry)

def transition(caller):
	common.stack.set_visible_child_full('newrep', Gtk.StackTransitionType.SLIDE_LEFT)
	common.win.set_title('New Repository')
	common.back_button.disconnect(common.back_button_signal_id)
	def exit_callback(caller):
		reset_error()
		transitions.to_addrep(None, Gtk.StackTransitionType.SLIDE_RIGHT)
	common.back_button_signal_id = common.back_button.connect('clicked', exit_callback)

def create_repository(caller):
	#validate entries
	reset_error()
	valid = True
	name = directory_name_entry.get_text()
	if name == '':
		common.set_error(directory_name_entry)
		directory_name_entry.empty_popover.show_all()
		valid = False

	args = argparse.Namespace()
	args.encryption = 'none'
	if not encryption_disable_checkbox.get_active():
		passwd = encryption_passphrase_entry.get_text()
		if passwd == '':
			common.set_error(encryption_passphrase_entry)
			common.set_error(encryption_passphrase_again_entry)
			encryption_passphrase_entry.popover.show_all()
			valid = False
		elif passwd != encryption_passphrase_again_entry.get_text():
			common.set_error(encryption_passphrase_entry)
			common.set_error(encryption_passphrase_again_entry)
			encryption_passphrase_again_entry.popover.show_all()
			valid = False
		elif valid:
			repository.set_pass(passwd)
			if encryption_store_key_checkbox.get_active():
				args.encryption = 'keyfile'
			else:
				args.encryption = 'repokey'

	directory = directory_path_button.get_filename()
	if directory:
		path = os.path.join(directory_path_button.get_filename(), name)
		if os.path.exists(path) and valid:
			dialog = Gtk.MessageDialog(common.win, Gtk.DialogFlags.MODAL, Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE,
			                           'The file [' + path + '] already exists. Choose a different location or name')
			dialog.run()
			dialog.destroy()
			valid = False
	else:
		common.set_error(directory_path_button)
		directory_path_button.popover.show_all()
		valid = False

	if valid:
		transitions.to_load()

		def idle_func():
			common.cur_path = os.path.join(directory_path_button.get_filename(), name)
			common.prepare()

			#Simulate do_init, Create repository, cache and manifest and lock them
			common.cur_repository = borg.repository.Repository(common.cur_path, create=True, exclusive=True, lock_wait=1)
			common.cur_repository.__enter__()
			borg.archiver.logger.info('Initializing repository at "%s"' % common.cur_path)
			common.cur_rep_key = borg.key.key_creator(common.cur_repository, args)
			common.cur_rep_manifest = borg.helpers.Manifest(common.cur_rep_key, common.cur_repository)
			common.cur_rep_manifest.key = common.cur_rep_key
			common.cur_rep_manifest.write()
			common.cur_repository.commit()
			common.cur_rep_cache = borg.cache.Cache(common.cur_repository, common.cur_rep_key, common.cur_rep_manifest, lock_wait=1,
			                                 warn_if_unencrypted=False)
			common.cur_rep_cache.__enter__()

			repository.start()

		GLib.idle_add(idle_func)

def setup(caller):
	global button_signal_id, directory_path_button, directory_name_entry, encryption_disable_checkbox, encryption_store_key_checkbox
	global encryption_passphrase_entry, encryption_passphrase_again_entry
	#Setup new repository options
	builder = Gtk.Builder.new_from_file('../data/ui/newrep.ui')

	grid = builder.get_object('grid')
	common.stack.add_named(grid, 'newrep')

	#Fill new repository options
	directory_name_entry = builder.get_object('directory_name_entry')
	directory_name_entry.empty_popover = common.error_popover(directory_name_entry, 'A name is required', Gtk.PositionType.TOP)
	directory_path_button = builder.get_object('directory_path_button')
	directory_path_button.popover = common.error_popover(directory_path_button, 'A location for the repository is required',
	                                                     Gtk.PositionType.BOTTOM, 'file-set')

	encryption_passphrase_entry = builder.get_object('encryption_passphrase_entry')
	encryption_passphrase_again_entry = builder.get_object('encryption_passphrase_again_entry')
	encryption_passphrase_entry.popover = common.error_popover(encryption_passphrase_entry, 'Passphrases required for encryption',
	                                                           Gtk.PositionType.TOP)
	encryption_passphrase_again_entry.popover = common.error_popover(encryption_passphrase_again_entry, 'Passphrases do not match',
	                                                                 Gtk.PositionType.BOTTOM)
	encryption_store_key_checkbox = builder.get_object('encryption_store_key_checkbox')
	encryption_disable_checkbox = builder.get_object('encryption_disable_checkbox')
	encryption_disable_checkbox.set_halign(Gtk.Align.START)
	encryption_passphrase_label = builder.get_object('encryption_passphrase_label')
	encryption_passphrase_again_label = builder.get_object('encryption_passphrase_again_label')

	def toggle_encryption(caller):
		not_active = not caller.get_active()
		encryption_passphrase_label.set_sensitive(not_active)
		encryption_passphrase_entry.set_sensitive(not_active)
		encryption_passphrase_again_label.set_sensitive(not_active)
		encryption_passphrase_again_entry.set_sensitive(not_active)
		encryption_store_key_checkbox.set_sensitive(not_active)
		if not not_active:
			encryption_passphrase_entry.popover.hide()
			encryption_passphrase_again_entry.popover.hide()
			common.remove_error(encryption_passphrase_entry)
			common.remove_error(encryption_passphrase_again_entry)
	builder.connect_signals({'block_slash' : common.block_slash,
	                         'toggle_encryption' : toggle_encryption,
	                         'create_repository' : create_repository})

	#reconnect caller to skip widget setup
	caller.disconnect(button_signal_id)
	caller.connect('clicked', transition)

	transition(caller)
