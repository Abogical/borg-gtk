import common, replist

import os
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, Gdk

def to_replist(caller):
	replist.stack_transition(Gtk.StackTransitionType.CROSSFADE)
	common.win.set_title('Repositories')
	common.win.get_titlebar().set_subtitle(None)
	common.connect_back_button(lambda caller: caller)
	common.back_button.hide()
	common.addrep_button.show()

def to_addrep(caller, transition):
	common.stack.set_visible_child_full('add', transition)
	common.addrep_button.hide()
	common.back_button.show()
	common.win.set_title('Add repository')
	common.connect_back_button(to_replist)

def to_rep(transition=Gtk.StackTransitionType.CROSSFADE):
	common.stack.set_visible_child_full('rep', transition)
	common.addrep_button.hide()
	common.back_button.show()
	common.win.set_title('Repository')
	common.win.get_titlebar().set_subtitle(replist.simplest_path(common.cur_path))
	def back_func(caller):
		common.unset_cur_repository(None)
		to_replist(caller)
	common.connect_back_button(back_func)

def to_create_form(caller, transition=Gtk.StackTransitionType.SLIDE_LEFT):
	common.stack.set_visible_child_full('create_form', transition)
	common.win.set_title('Create archive')
	common.connect_back_button(lambda caller: to_rep(Gtk.StackTransitionType.SLIDE_RIGHT))

def all_widgets_sensitive(boolean):
	common.stack.set_sensitive(boolean)
	common.addrep_button.set_sensitive(boolean)
	common.back_button.set_sensitive(boolean)

def to_load():
	all_widgets_sensitive(False)
	common.set_load_cursor()

def unload():
	all_widgets_sensitive(True)
	common.remove_load_cursor()
