import borg
import importlib
importlib.import_module('.logger', 'borg')
importlib.import_module('.helpers', 'borg')
importlib.import_module('.cache', 'borg')
importlib.import_module('.archive', 'borg')

import os, signal, gi, pwd, grp
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GObject

config_data = {}

def connect_back_button_one_time(func):
	def callback(caller):
		func()
		back_button.disconnect(handler_id)
	handler_id = back_button.connect('clicked', callback)
	return handler_id

def connect_back_button(func, *args):
	global back_button_signal_id
	back_button.disconnect(back_button_signal_id)
	back_button_signal_id = back_button.connect('clicked', func, *args)

def run_msg_dialog(msg_type, msg_str, msg_str_2=None):
	msg_dialog = Gtk.MessageDialog(win, Gtk.DialogFlags.MODAL, msg_type, Gtk.ButtonsType.CLOSE, msg_str)
	msg_dialog.set_property('use-markup', True)
	msg_dialog.format_secondary_markup(msg_str_2)
	msg_dialog.run()
	msg_dialog.destroy()

not_prepared = True
def prepare():
	global not_prepared
	if not_prepared:
		archiver.lock_wait = 1
		borg.logger.setup_logging(level='debug', is_serve=False)
		borg.helpers.check_extension_modules()
		if borg.helpers.is_slow_msgpack():
			borg.archiver.logger.warning("Using a pure-python msgpack! This will result in lower performance.")
		not_prepared = False

def set_cur_repository(location, create):
	global cur_repository, cur_rep_manifest, cur_rep_key, cur_rep_cache
	cur_repository = borg.repository.Repository(location, create=create, exclusive=True, lock_wait=1)
	cur_repository.__enter__()
	cur_rep_manifest, cur_rep_key = borg.helpers.Manifest.load(cur_repository)
	cur_rep_cache = borg.cache.Cache(cur_repository, cur_rep_key, cur_rep_manifest, lock_wait=1)
	cur_rep_cache.__enter__()

def get_archive(name, create):
	return borg.archive.Archive(cur_repository, cur_rep_key, cur_rep_manifest, name, cache=cur_rep_cache, create=create)

def unset_cur_repository(exc):
	global cur_rep_manifest, cur_rep_key, cur_rep_cache, cur_repository, archive_liststore
	del cur_rep_manifest
	del cur_rep_key
	args = (type(exc), exc, None)
	if cur_rep_cache:
		cur_rep_cache.__exit__(*args)
	del cur_rep_cache
	cur_repository.__exit__(*args)
	del cur_repository

def fill_archive_liststore():
	archive_liststore.clear()
	for archive_info in cur_rep_manifest.list_archive_infos(sort_by='ts'):
		archive_liststore.append([borg.helpers.format_time(borg.helpers.to_localtime(archive_info.ts)),
		                          archive_info.name, None])

def reload_cur_repository():
	#TODO: try refreshing without realeasing the lock
	unset_cur_repository(None)
	set_cur_repository(cur_path, False)
	#-------------------------------------------------
	fill_archive_liststore()

def flush_display():
	Gdk.Display.get_default().flush()

def filechooser_dialog(title, action):
	return Gtk.FileChooserNative.new(title, win, action)

def get_file(dialog):
	filename = None
	if dialog.run() == Gtk.ResponseType.ACCEPT:
		filename = dialog.get_filename()
	dialog.destroy()
	flush_display()
	return filename

def set_load_cursor():
	win.get_window().set_cursor(Gdk.Cursor.new_for_display(Gdk.Display.get_default(), Gdk.CursorType.WATCH))

def remove_load_cursor():
	win.get_window().set_cursor(None)

def set_error(widget):
	widget.get_style_context().add_class(Gtk.STYLE_CLASS_ERROR)

def remove_error(widget):
	widget.get_style_context().remove_class(Gtk.STYLE_CLASS_ERROR)

def set_margin_all(widget, num):
	widget.set_margin_top(num)
	widget.set_margin_bottom(num)
	widget.set_margin_start(num)
	widget.set_margin_end(num)
	return widget

def block_slash(editable, new_text, new_text_len, pos):
	if '/' in new_text:
		GObject.signal_stop_emission_by_name(editable, 'insert-text')

def error_popover(parent, text, position, hide_signal='focus-in-event'):
	popover = Gtk.Popover.new(parent)
	popover.set_modal(False)
	popover.set_position(position)
	popover.add(set_margin_all(Gtk.Label(text), 5))
	parent.connect(hide_signal, lambda *args: popover.hide())
	return popover

