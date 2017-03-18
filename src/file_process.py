import enums

import borg, importlib
importlib.import_module('.helpers', 'borg')
importlib.import_module('.archive', 'borg')
importlib.import_module('.xattr', 'borg')

import os, stat, queue, threading, time, datetime, gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

def walk(path):
	global total_size, total_n_files
	st = os.lstat(path)

	if (st.st_ino, st.st_dev) in skip_inodes:
		return

	for pat in exclude_list:
		if pat.match(path):
			return

	metadata = {}
	metadata[b'name'] = os.path.basename(path)

	for key in ['mode', 'atime', 'mtime', 'ctime', 'uid', 'gid']:
		metadata[key.encode()] = getattr(st, 'st_'+key)

	is_dir = stat.S_ISDIR(st.st_mode)
	size_to_put = st.st_size
	if is_dir:
		size_to_put = 0

	# get the parent path
	parent_treepath = treepath.copy()
	parent_treepath.up()

	mp_queue.put((enums.ADDED, parent_treepath.to_string(), metadata, size_to_put))
	if not_preview:
		treepath_string = treepath.to_string()
		t_queue.put((path, st, treepath_string))

	if is_dir:
		treepath.down()
		for entry in os.listdir(path):
			walk(os.path.join(path, entry))
		treepath.up()
		if not_preview:
			t_queue.put((enums.DONE, treepath_string))
	treepath.next()

def add_items(buffer_local_thread):
	borg.xattr.buffer._thread_local.buffer = buffer_local_thread
	borg.compress.buffer._thread_local.buffer = buffer_local_thread
	while True:
		entry = t_queue.get()
		if entry == None:
			return
		if entry[0] == enums.DONE:
			mp_queue.put(entry)
			continue
		path, st, entry_treepath = entry[0:3]
		mp_queue.put((enums.PROCESSING, entry_treepath, path))
		try:
			# TODO: this needs to support more types of files
			if stat.S_ISREG(st.st_mode):
				archive.process_file(path, st, archive.cache)
				mp_queue.put((enums.DONE, entry_treepath))
			elif stat.S_ISDIR(st.st_mode):
				archive.process_dir(path, st)
			elif stat.S_ISLNK(st.st_mode):
				archive.process_symlink(path, st)
				mp_queue.put((enums.DONE, entry_treepath))
		except borg.archive.BackupOSError as e:
			mp_queue.put((enums.ERROR, entry_treepath, path, e))

def send_stats():
	mp_queue.put((enums.STATS_UPDATE, archive.stats.osize, archive.stats.csize, archive.stats.usize, archive.stats.nfiles))

def stats_update():
	prev_osize, prev_csize, prev_usize, prev_nfiles = 0, 0, 0, 0
	while stats_update_thread_continue:
		time.sleep(0.1)
		stats = archive.stats
		if (prev_osize, prev_csize, prev_usize, prev_nfiles) != (stats.osize, stats.csize, stats.usize, stats.nfiles):
			send_stats()
			prev_osize, prev_csize, prev_usize, prev_nfiles = stats.osize, stats.csize, stats.usize, stats.nfiles

def setup_skip_inodes(rep_path):
	global skip_inodes
	skip_inodes = set()
	def skip_path(path):
		try:
			st = os.stat(path)
			skip_inodes.add((st.st_ino, st.st_dev))
		except OSError:
			pass

	skip_path(borg.helpers.get_cache_dir())
	skip_path(rep_path)

def walk_liststore(include_liststore):
	for row in include_liststore:
		walk(row[0])

def preview(_mp_queue, include_liststore, _exclude_list, rep_path):
	global mp_queue, exclude_list, not_preview, treepath
	not_preview = False
	mp_queue = _mp_queue
	exclude_list = _exclude_list
	treepath = Gtk.TreePath.new_first()
	setup_skip_inodes(rep_path)
	walk_liststore(include_liststore)
	mp_queue.put((enums.ALL_ADDED,))

def create(_mp_queue, include_liststore, _exclude_list, rep_path, buffer_local_thread, _archive):
	global total_size, total_n_files, mp_queue, t_queue, exclude_list, archive, skip_inodes, treepath
	global stats_update_thread, not_preview, stats_update_thread_continue
	not_preview = True
	total_size, total_n_files = 0, 0
	treepath = Gtk.TreePath.new_first()
	mp_queue, t_queue = _mp_queue, queue.Queue()
	archive, exclude_list = _archive, _exclude_list

	stats_update_thread_continue = True

	setup_skip_inodes(rep_path)

	add_items_thread = threading.Thread(target=add_items, args=(buffer_local_thread,), daemon=True)
	stats_update_thread = threading.Thread(target=stats_update, daemon=True)
	add_items_thread.start()
	stats_update_thread.start()

	walk_liststore(include_liststore)

	mp_queue.put((enums.ALL_ADDED,))
	t_queue.put(None)

	add_items_thread.join()
	stats_update_thread_continue = False
	stats_update_thread.join()
	archive.save()
	send_stats()
	mp_queue.put((enums.COMPLETE, borg.helpers.format_time(borg.helpers.to_localtime(archive.start.replace(tzinfo=datetime.timezone.utc))),
	              archive.name))
