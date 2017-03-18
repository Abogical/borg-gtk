#!/usr/bin/env python3
import common, replist, repository, addrep, transitions

import borg
import importlib
importlib.import_module('.archiver', 'borg')

import os
import json
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, Gio

def escape_key_release(caller, event):
	if event.keyval == Gdk.KEY_Escape:
		common.back_button.clicked()
		return True
	return False

#startup
def startup(app):
	builder = Gtk.Builder.new_from_file('../data/ui/main.ui')

	common.win = builder.get_object('win')
	common.stack = builder.get_object('stack')

	common.back_button = builder.get_object('back_button')
	common.back_button_signal_id = common.back_button.connect('clicked', lambda caller: caller)

	common.addrep_button = builder.get_object('addrep_button')
	addrep.button_signal_id = common.addrep_button.connect('clicked', addrep.setup)

	common.stop_button = builder.get_object('stop_button')
	common.stop_button_signal_id = common.stop_button.connect('clicked', lambda caller: caller)

	#Setup repository list
	common.config_file = os.fdopen(os.open(os.path.expanduser('~/.config/borg-gtk.json'), os.O_RDWR | os.O_CREAT), 'r+')

	replist.listbox = builder.get_object('replist_listbox')
	replist.listbox.set_sort_func(lambda row1, row2: row2.time - row1.time)

	builder.connect_signals({'escape_key_release' : escape_key_release,
	                         'row-activated' : lambda caller, row: repository.start_with_path(row.path)})

	repository.set_pass('')
	os.environ['BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK'] = 'yes'
	os.environ['BORG_RELOCATED_REPO_ACCESS_IS_OK'] = 'yes'
	os.environ['BORG_DELETE_I_KNOW_WHAT_I_AM_DOING'] = 'yes'

	replist.refresh()

	common.archiver = borg.archiver.Archiver()

	replist.stack_transition(Gtk.StackTransitionType.NONE)


#activation or when a second instance has started
def activate(app):
	app.add_window(common.win)
	common.win.show()

def shutdown(app):
	common.config_file.close()
	if getattr(common, 'cur_repository', None):
		common.unset_cur_repository(None)

common.app = Gtk.Application.new('apps.borg-gtk', Gio.ApplicationFlags.NON_UNIQUE)
common.app.connect('startup', startup)
common.app.connect('activate', activate)
common.app.connect('shutdown', shutdown)

exit(common.app.run())
