**THIS PROGRAM IS UNSTABLE AND INCOMPLETE. DO NOT USE IT FOR YOUR BACKUPS! ONLY USE IT TO TEST THIS PROGRAM.**

borg-gtk
=

borg-gtk is a GTK+ frontend for the borg backup utility. The project has been stopped as there's now an official API for borg.

Commands wrapped by this program:

- `init`
- `info`
- `list` (repository and archive)
- `create`
- `delete`

According to ctime, This project was started as early as 17/3/2016

---
Screenshots
-
<img src="https://cloud.githubusercontent.com/assets/10688496/24120963/27282756-0dbf-11e7-9c1c-ebc52f6a6273.png" height="400"/>
<img src="https://cloud.githubusercontent.com/assets/10688496/24120858/ca514c1a-0dbe-11e7-981a-ede8059967ef.png" height="400"/>

---

Implementation
-
borg-gtk uses an unstable approach for a front-end as it imports the borg python code and uses it directly, rather than using the JSON API. This is because it was written almost a year before the JSON API was created, and using a subprocess was too limited and slow.

Added Features
-
With access to the borg code directly, borg-gtk adds features not present in borg. For example:

- A real progressbar for creating an archive, shows which files to process, and which are pending
- 'Opening' a repository and doing multiple operations in one go, as if it's a borg shell.
- Calculating the size and compressed size of folders in archives

Usage
-
Run the following:

```bash
$ cd ./src
$ ./main.py
```

Note: This will create a `borg-gtk.json` file in `~/.cache`

---
**It's incomplete, why share it?**

- The added features could prove to be beneficial for the main borg project.
- Those who want to create a front-end for borg may also find this useful.

**Why not continue the project?**

- The API is too limited to provide some of the added features currently in the project.
- Continuing with my implementation is a bad idea as it's officially unsupported.
- Supporting the new API will require a complete rewrite
- Gtk+ was probably a bad choice. Qt has better cross-platform support.




