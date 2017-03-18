import enums

import borg, importlib
importlib.import_module('.helpers', 'borg')
importlib.import_module('.archive', 'borg')

import os, stat, queue, gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

def walk():
	treepath = Gtk.TreePath.new_first()
	dir_stack = []

	def pop_dir_item():
		nonlocal treepath
		dir_item, treepath = dir_stack.pop()
		if is_extract:
			t_queue.put((enums.DONE, treepath.to_string(), dir_item))
		treepath.next()

	for item in archive.iter_items():
		metadata = {}
		for key in [b'mode', b'atime', b'mtime', b'ctime', b'uid', b'user', b'gid', b'group']:
			metadata[key] = item[key]
		path = item[b'path']
		metadata[b'name'] = os.path.basename(path)

		while dir_stack and not path.startswith(dir_stack[-1][0][b'path']):
			pop_dir_item()

		parent_treepath = treepath.copy()
		parent_treepath.up()
		mp_queue.put((enums.ADDED, parent_treepath.to_string(), path, item.get(b'chunks', None), metadata))

		if is_extract:
			t_queue.put((enums.ADDED, path, item, treepath.to_string()))

		if stat.S_ISDIR(item[b'mode']):
			dir_stack.append((item, treepath.copy()))
			treepath.down()
		else:
			treepath.next()
	mp_queue.put((enums.ALL_ADDED,))
	while dir_stack:
		pop_dir_item()
	if is_extract:
		t_queue.put(None)

def extract_item():
	while True:
		entry = t_queue.get()
		if entry == None:
			return
		path, item, treepath = entry

def list(_mp_queue, _archive):
	global archive, mp_queue, is_extract
	is_extract = False
	mp_queue, archive = _mp_queue, _archive
	walk()
