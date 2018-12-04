WatchDog
=======

A Python-based After Effects “aerender” front end that supports watch folder style rendering for primarily frame based projects.

This version of the script was first used successfully in production across 8 workstations, each with 3-5 instances of aerender running. This was in full production for AE CC in 2013.

WatchDog can launch several instances of Adobe A!er E"ects on Macintosh (Currently) computer platforms, and act in a manner similar to the internal Watch Folder render queue. It is more stable in that it does not collide several processes while accessing the render control file. It requires fewer resources to run in the background via a simple terminal command, than launching multiple GUI render engines. Watchdog can be launched across a network of machines to a common server, and turn a small number of multi-core machines into a large render resource.

History
=======

WatchDog was first developed in 2013 to handle the rendering needs for a small VFX team doing Digital makeup (dMFX) For TNT’s Falling Skies. It has been used on film, television, multimedia, and theme park attractions ever since to create stunning images for your entertainment.

Production use in:
==================
Falling Skies
The Strain
The Librarians Hemlock Grove
Dumb and Dumber Too American Gods
and more...


WatchDog is a Python script that needs to be placed in a specific computer system directory (details in the install ReadMe file), followed with a few simple terminal commands. It will be necessary for you to have administrative access to properly install the files.
Currently WatchDog is only supported on Macintosh platforms of any size, including laptops. It requires a full AE install from Creative Cloud, but it is capable of “headless” rendering — which avoids using precious Adobe licenses up too quickly.

To build a headless rendering node, create a blank text file named “ae_render_only_node.txt” installed in the home directory so that the render engines launch without issue, as long as all plug-ins are also installed. This render node designation file is a standard Adobe thing, not something directly required by WatchDog. It will force any installed AE license to run as a render engine, so do NOT install this in a machine you will be using with an active Adobe AE license.

Cost
====
WatchDog is Free Shareware, and set up on GitHub for open source development within the Adobe After Effects community of developers. 

WatchDog is published as-is, and has no support, outside of somehow bribing the original developer with candies, endless money, or a dedicated freeway lane! Seriously. Open source. Free. As-is. Hoping for your contribution, or at least its use.

INSTALLATION
============

To install WatchDog you must make a copy of the master file into the /usr/local/bin directory of a properly set up workstation. The file should have the ”.py” extension removed and the mode for the file set to executable (chmod a+x watchdog)

If you are installing without macports you should use python 2.6 or 2.7 and you can put the executable in any system PATH accessible location.

You can edit the AERENDER path in the python file to point to the desired render engine.

Make sure the first line in the file reads     #! /usr/bin/python 


INSTALLATION with MACPORTS
============

To install WatchDog you must make a copy of the master file into the /opt/local/bin directory of a properly set up workstation. The file should have the ”.py” extension removed and the mode for the file set to executable (chmod a+x watchdog)

Note that the /opt/local/bin directory is installed by MacPorts as part of the new machine set up process - this also installs the correct version of Python necessary to run the script. Install WatchDog AFTER the procedures in the IT section are followed.

You can edit the AERENDER path in the python file to point to the desired render engine.

Make sure the first line in the file reads     #! /opt/local/bin/python 




Rendering with WatchDog For MAC WORKSTATIONS Only
==========================================
For the macs in production we have developed a script called WatchDog that enables After Effects to render using the aerender module instead of a GUI copy of After Effects (AE). The script utilizes existing AE watchfolder collecting tools to speed up processing of AE projects - both on a single machine and with multiple machines.

USE:

1. Open the Terminal application and type:

```
watchdog -n 2 -w path/to/the/watchfolder
```

the number 2 can be replaced with other numbers and represents the number of aerender insqances that will be started on this machine. It is safe to use n = 1/2 of the number of cores on your machine if you will ONLY be rendering.

Note: it is possible to continue working in AE while you let WatchDog watch a folder. If you need to keep working use a low number of instances so that your machine does not bog down.

the path to the watchfolder can be on a network volume but all machines attempting to render must have access to all the necessary files (this is similar to a watchfolder render)

to stop WatchDog from running, use control-C in the terminal window where it is running.


OTHER INFO:
===========
WatchDog works in cooperation with Watch Folder renders so it should be possible to use them both at the same time. WatchDog will not pick up a project that has been completed by a watch-render and it sets stop files that will keep watch renders from starting after WatchDog has run successfully.

There are logs kept for each individual instance of aerender running on every machine in the “WatchDog Logs” folder that is along side the rendered project file. Using these you can track frame problems back to an individual machine and there is a script available to delete all frames rendered by that instance (more info to come here)

WARNINGS
========
WatchDog is expected to fail for all except 1 instance when rendering a movie. WatchDog works best with frame renders that are set up to optimize for skip-frame rendering (similar to the watch folder). If you need to include movie files in your project be aware that multiple machines will NOT work on the render and if there are movies before other frames in the Render Queue of the project, you will end up with only one instance working on everything after the movie.

It is best to render any movie files at the end of the render queue to avoid losing extra render power.

Every effort has been made to have WatchDog clean up bad dpx frames after a render but if you are rendering to other formats there may be small or zero-size frames left behind if WatchDog is quit early, or if it crashes.

