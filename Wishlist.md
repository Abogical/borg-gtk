Given from my experience of creating this program, here are two features I wish I can have with borg. These features already exist in this project.

borg shell
-
[This has already been mentioned](https://github.com/borgbackup/borg/issues/1104), This is useful for frontends, since this adds the ability to 'open' a repository. Simply write the password, then do as many commands as you wish, without having to reload the repository over and over again.

I've tried using the subprocess implementation with borg, where you invoke borg for every command. It turned out that this made the application very unresponsive and slow.

Create progress
-
I've implemented a progress which shows an actual percentage of completion. A progressbar, original size processed / total original size and files processed / total files. This doesn't exist in `borg create --progress`.

It's not perfect. My implementation has bugs, processed and totals don't always match up at the end. Nevertheless here's how it works.

---

The way it's done is separating the create process into three threads. Let's name them as:

- The Finder
- The Worker
- The Reporter

Two Queues will also be used:

- The reporter has a queue that recieves messages from the finder and the worker.
- The worker has a queue that recieves messages only from the finder

**The Finder**

The finder is responsible for walking through the directory that will be archived. It will look through all the include patterns, and exclude the exclude patterns. Every time it finds a file to include in the archive, it does the following:

1. Call `os.stat()` on the file, get the size of the file.
2. Talk to the reporter via a queue, give him the path and size of the file
3. Talk to the worker via a queue, give him the path and stat of the file

Once all the files are added, It talks to the reporter saying that all the files has been added.

**The Worker**

The worker does the actual job of putting the file in the archive and adding the item to the archive. It recieves the paths and stat of the file from the finder via the queue, Then adds the file as an item in the archive via `archive.add_item()`. 

Once it's done it talks to the reporter, giving him the path of the file that is done processing.

**The Reporter**

The reporter puts it all together. It recieves both messages from the finder and the reporter via the queue. It has a total size counter and a total file counter.

When it recieves messages from the finder for files to include, it adds the size of the file to the size counter, and adds the file counter by one.

When it recieves messages from the worker for files that are done. It can print which file has been done processing.

When it recieves the message that all files have been added. The reporter can calculate an actual percentage of completion. It can get the number of files and size processed via `archive.stats` and thus calculate files processed / total number of files, etc.

---

In this approach, there is a delay between recognizing the file and adding to the archive. This has the following disadvantages:

- A file that has been moved during the delay will not be added, and attempting to add it to the archive will create an exception.
- If a file is edited during this delay, it's stat may turn inaccurate.
	- This may be solved by giving the option to stat the file at the worker thread instead of the finder thread, this removes the functionality of calculating the total size in the  expense of being safer.
- The bigger the delay, the more files end up waiting at the queue. This consumes memory. This is caused if the worker thread is taking time adding a huge file.

This obviously requires multithreading, so this is something to consider for the multithreading branch of borg.

I hope this feedback helps :)




