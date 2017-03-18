import common, newrep, transitions, repository

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

def choose_path(caller):
	result = common.get_file(common.filechooser_dialog('Open repository', Gtk.FileChooserAction.SELECT_FOLDER))

	if result:
		repository.start_with_path(result)

def setup(caller):
	builder = Gtk.Builder.new_from_file('../data/ui/addrep.ui')

	common.stack.add_named(builder.get_object('grid'), 'add')

	newrep.button_signal_id = builder.get_object('newrep_button').connect('clicked', newrep.setup)

	common.addrep_button.disconnect(button_signal_id)
	common.addrep_button.connect('clicked', transitions.to_addrep, Gtk.StackTransitionType.CROSSFADE)

	builder.connect_signals({'choose_path': choose_path})

	transitions.to_addrep(caller, Gtk.StackTransitionType.CROSSFADE)
