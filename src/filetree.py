import common, enums

import borg, importlib
importlib.import_module('.helpers', 'borg')
importlib.import_module('.fuse', 'borg')

import os, stat, pwd, grp, gi, collections
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, GObject

def toggle_hide_column(checkbox, column):
	column.set_visible(checkbox.get_active())

class FileModel(Gtk.TreeStore):
	metadata_cache_left = 128

	def unref_node(self, iterator):
		if self[iterator][0] != None:
			self.metadata_cache_left += 1
			self[iterator][0] = None
		return super().unref_node(iterator)

def name_and_id(name, name_id):
	if name != None:
		return '%s (%s)' % (name, name_id)
	else:
		return str(name_id)

def size_data_func(col, cell, model, iterator, index):
	cell.set_property('text', borg.helpers.format_file_size(model[iterator][index]))

class BaseFileTree:
	cache = borg.fuse.ItemCache()

	def icon_data_func(self, col, cell, model, iterator, data):
		if model.iter_has_child(iterator):
			return cell.set_property('icon-name', 'folder')
		metadata = self._load_metadata(iterator)
		if stat.S_ISDIR(metadata[b'mode']):
			return cell.set_property('icon-name', 'folder')
		cell.set_property('gicon',
		                  Gio.content_type_get_icon(Gio.content_type_guess(metadata[b'name'])[0]))

	def name_data_func(self, col, cell, model, iterator, data):
		cell.set_property('text', self._load_metadata(iterator)[b'name'])

	def mode_data_func(self, col, cell, model, iterator, data):
		cell.set_property('text', stat.filemode(self._load_metadata(iterator)[b'mode']))

	def time_data_func(self, col, cell, model, iterator, key):
		metadata = self._load_metadata(iterator)
		cell.set_property('text',
		                  borg.helpers.format_time(borg.helpers.safe_timestamp(metadata[key])))

	def status_data_func(self, col, cell, model, iterator, data):
		cell.set_property('icon-name',
		      [None, 'emblem-synchronizing', 'process-completed-symbolic',
		      'process-error-symbolic'][model[iterator][self.status_column_index]])

	def _set_data_func(self, col, func, data=None):
		getattr(self, col + '_column').set_cell_data_func(
		                                self.builder.get_object(col + '_cellrenderer'), func, data)

	def __init__(self, status):
		self.status = status
		self.builder = Gtk.Builder.new_from_file('../data/ui/filetree.ui')

		def _set_from_builder(attr):
			setattr(self, attr, self.builder.get_object(attr))

		_set_from_builder('grid')
		_set_from_builder('treeview')
		_set_from_builder('checkbutton_grid')
		_set_from_builder('name_column')

		signal_set = {}

		def _set_column(col):
			col = col + '_column'
			obj = self.builder.get_object(col)
			setattr(self, col, obj)
			signal_set['toggle_'+col] = (toggle_hide_column, obj)

		self.name_column.set_cell_data_func(self.builder.get_object('name_cellrenderer'),
		                                    self.name_data_func)
		self.name_column.set_cell_data_func(self.builder.get_object('icon_cellrenderer'),
		                                    self.icon_data_func)
		_set_column('size')
		self._set_data_func('size', size_data_func, 2)
		_set_column('mode')
		self._set_data_func('mode', self.mode_data_func)
		_set_column('user')
		_set_column('group')
		_set_column('atime')
		self._set_data_func('atime', self.time_data_func, b'atime')
		_set_column('mtime')
		self._set_data_func('mtime', self.time_data_func, b'mtime')
		_set_column('ctime')
		self._set_data_func('ctime', self.time_data_func, b'ctime')

		self.builder.connect_signals(signal_set)

		store_cols = [GObject.TYPE_PYOBJECT, GObject.TYPE_INT64, GObject.TYPE_INT64]
		store_cols += self._setup_cols()
		del self.builder

		if status:
			self.status_column_index = len(store_cols)
			store_cols.append(int)

			self.status_cellrenderer = Gtk.CellRendererPixbuf()
			self.status_column = Gtk.TreeViewColumn('Status', self.status_cellrenderer)
			self.status_column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
			self.treeview.insert_column(self.status_column, -1)

			self.status_column.set_cell_data_func(self.status_cellrenderer, self.status_data_func)

			self.treeview.insert_column(self.status_column, -1)

			self.status_checkbutton = Gtk.CheckButton('Status')
			self.status_checkbutton.connect('toggled', toggle_hide_column, self.status_column)
			self.status_checkbutton.set_active(True)
			self.status_checkbutton.show()
			self.checkbutton_grid.insert_row(0)
			self.checkbutton_grid.attach(self.status_checkbutton, 0, 0, 2, 1)

		self.model = FileModel(*store_cols)
		self.treeview.set_model(self.model)

	def append(self, parent, arr, metadata, size):
		prepend_arr = [None, self.cache.add(metadata), size]
		if self.model.metadata_cache_left > 0:
			prepend_arr[0] = metadata
			self.model.metadata_cache_left -= 1
		if self.status:
			arr.append(enums.ADDED)
		return self.model.append(parent, prepend_arr + arr)

	def set_error_status(self, iterator):
		self.model[iterator][self.status_column_index] = enums.ERROR
		parent_iter = self.model.iter_parent(iterator)
		if parent_iter != None:
			self.set_error_status(parent_iter)

	def _load_metadata(self, iterator):
		if self.model[iterator][0] == None:
			metadata = self.cache.get(self.model[iterator][1])
			for key, value in metadata.items():
				if isinstance(value, bytes):
					value = value.decode()
				metadata[key] = value
			self.model[iterator][0] = metadata
			self.model.metadata_cache_left -= 1
		return self.model[iterator][0]

	def get_iter_from_string(self, treepath):
		if treepath == None:
			return None
		return self.model.get_iter_from_string(treepath)

	def set_processing_status_treepath(self, treepath):
		self.model[self.get_iter_from_string(treepath)][self.status_column_index] = enums.PROCESSING

	def set_done_status_treepath(self, treepath):
		self.model[self.get_iter_from_string(treepath)][self.status_column_index] = enums.DONE

	def set_error_status_treepath(self, treepath):
		self.set_error_status(self.get_iter_from_string(treepath))

class FileTree(BaseFileTree):
	def file_user_data_func(self, col, cell, model, iterator, data):
		uid = self._load_metadata(iterator)[b'uid']
		cell.set_property('text', name_and_id(pwd.getpwuid(uid)[0], uid))

	def file_group_data_func(self, col, cell, model, iterator, data):
		gid = self._load_metadata(iterator)[b'gid']
		cell.set_property('text', name_and_id(grp.getgrgid(gid)[0], gid))

	def _setup_cols(self):
		self._set_data_func('user', self.file_user_data_func)
		self._set_data_func('group', self.file_group_data_func)
		return []

	def _update_parent_size(self, iterator, size):
		self.model[iterator][2] += size
		parent_iter = self.model.iter_parent(iterator)
		if parent_iter != None:
			self._update_parent_size(parent_iter, size)

	def append(self, parent_treepath, metadata, size):
		iterator = super().append(self.get_iter_from_string(parent_treepath), [], metadata, 0)
		self._update_parent_size(iterator, size)
		return iterator

class ArchiveTree(BaseFileTree):
	def archive_user_data_func(self, col, cell, model, iterator, data):
		metadata = self._load_metadata(iterator)
		cell.set_property('text', name_and_id(metadata[b'user'], metadata[b'uid']))

	def archive_group_data_func(self, col, cell, model, iterator, data):
		metadata = self._load_metadata(iterator)
		cell.set_property('text', name_and_id(metadata[b'group'], metadata[b'gid']))

	def _setup_cols(self):
		self._set_data_func('user', self.archive_user_data_func)
		self._set_data_func('group', self.archive_group_data_func)

		self.csize_cellrenderer = Gtk.CellRendererText()
		self.csize_column = Gtk.TreeViewColumn('Compressed size', self.csize_cellrenderer)
		self.csize_column.set_cell_data_func(self.csize_cellrenderer, size_data_func, 3)
		self.csize_column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
		self.treeview.insert_column(self.csize_column, 3)

		self.csize_checkbutton = Gtk.CheckButton('Compressed size')
		self.csize_checkbutton.connect('toggled', toggle_hide_column, self.csize_column)
		self.csize_checkbutton.set_active(True)
		self.csize_checkbutton.show()
		self.checkbutton_grid.attach(self.csize_checkbutton, 1, 0, 1, 1)

		self.chunks_cellrenderer = Gtk.CellRendererText()
		self.chunks_column = Gtk.TreeViewColumn('Chunks', self.chunks_cellrenderer, text=5)
		self.chunks_column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
		self.chunks_column.set_visible(False)
		self.treeview.insert_column(self.chunks_column, -1)

		self.chunks_checkbox = Gtk.CheckButton('Chunks')
		self.chunks_checkbox.connect('toggled', toggle_hide_column, self.chunks_column)
		self.chunks_checkbox.show()
		self.checkbutton_grid.attach(self.chunks_checkbox, 0, 4, 1, 1)

		self.uchunks_cellrenderer = Gtk.CellRendererText()
		self.uchunks_column = Gtk.TreeViewColumn('Unique chunks', self.uchunks_cellrenderer,
		                                         text=4)
		self.uchunks_column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
		self.uchunks_column.set_visible(False)
		self.treeview.insert_column(self.uchunks_column, -1)

		self.uchunks_checkbox = Gtk.CheckButton('Unique chunks')
		self.uchunks_checkbox.connect('toggled', toggle_hide_column, self.uchunks_column)
		self.uchunks_checkbox.show()
		self.checkbutton_grid.attach(self.uchunks_checkbox, 1, 4, 1, 1)

		return [GObject.TYPE_INT64]*3 + [GObject.TYPE_PYOBJECT]

	def _update_parent_totals(self, iterator, size, csize):
		self.model[iterator][2] += size
		self.model[iterator][3] += csize

		''' This doesn't work
		iterator_common_chunks = self.model[iterator][6]
		for common_key in iterator_common_chunks.keys() & common_chunks.keys():
			iterator_common_chunks[common_key] -= 1
			common_chunks[common_key] = iterator_common_chunks[common_key]
			if iterator_common_chunks[common_key] == 1:
				del iterator_common_chunks[common_key]
				del common_chunks[common_key]
				uchunks += 1
		self.model[iterator][4] += uchunks
		iterator_common_chunks.update(common_chunks)
		self.model[iterator][6] = iterator_common_chunks
		self.model[iterator][5] = self.model[iterator][4] + len(iterator_common_chunks)
		'''

		parent_iter = self.model.iter_parent(iterator)
		if parent_iter != None:
			self._update_parent_totals(parent_iter, size, csize)

	def append(self, parent_treepath, path, chunks, metadata):

		total_size, total_csize, total_uchunks, total_chunks = 0,0,0,0
		parent_iter = self.get_iter_from_string(parent_treepath)

		if chunks != None:
			# Stores a list of non-unique chunks, to calculate parent chunks and uchunks
			# common_chunks = {}
			for chunk_id, size, csize in chunks:
				total_chunks += 1
				total_size += size
				total_csize += csize
				'''
				chunk_refcount = common.cur_rep_cache.chunks[chunk_id][0]
				
				if chunk_refcount == 1:
					total_uchunks += 1
				else:
					common_chunks[chunk_id] = chunk_refcount
				'''
			if parent_iter != None:
				self._update_parent_totals(parent_iter, total_size, total_csize)
		

		iterator = super().append(parent_iter, [total_csize, total_uchunks, total_chunks, None], metadata, total_size)

		'''
		if stat.S_ISDIR(metadata[b'mode']):
			self.model[iterator][6] = {}
		'''
