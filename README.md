A series of tools for automating various tasks at ANU. Please **please** **please** **please** keep these to yourself.

### Install
These tools require Python 3.5 or newer.

```
pip install requests
pip install lxml
pip install keyring
pip install dateutil
pip install prompt-toolkit
```

Set your Wattle password for your uXXXXXX username into the keyring:

```
keyring set anu uXXXXXX
```

You can add a system variable called `WATTLE_USERNAME` that is set to your username. You will not be required to enter it as an argument to these tools.

### Tutorial Signup

An example command line call of the tutorial.py script follows: 
```
python tutorial.py -u uXXXXXX [--sched] [--watch] --groupid 902521 --id "Tutorial 06"
```

The `username` argument specifies the Wattle account to log in to, which you should have already added the password to the keychain.
The `groupid` argument is the numerical id of the group/tutorial sign-up page. This can be found by browsing to the tutorial sign up page and looking at the the numbers at the end of the URL.
The `id` argument is the tutorial slot that the script will attempt to join. This is the string found in the tutorial sign up table, in the left most column of the row of the slot you wish to join.
The `sched` switch will use the opening time of sign up, log in 20 seconds before and start trying to sign up 3 seconds before opening.

Without the `--sched` option it will start to hammer wattle as soon as the command is run. If this is desired, you would ideally start the script 5 seconds before the tutorial sign up opens to avoid any throttling or banning.

### Booking Library Rooms

This is an automated room booking script, the idea being that you use OS X's Automator and Scheduler to automatically book rooms, email participants the details and calendar invite.

```
pip install intervaltree
pip install tabulate
pip install dateutil
```

To list bookings at Chifley on a certain date:
```python librarybook.py -u uXXXXXX --rooms -L Chifley -D "10/08/16"```

To show free rooms at a certain time:
```python librarybook.py -u uXXXXXX --rooms --free -D "10/08/16 9:00"```

To make a booking:
```python librarybook.py -u uXXXXXX -L Hancock -R 3.09 -D "10/09/16 14:00"```

## EchoDL
Install python libraries
```
pip install tabulate
pip install dateutil
```

First make the Echo DL directory:
```
mkdir ~/EchoDL
```

Do an initial run of EchoDL to set up the subscriptions:
```
python echodl.py
```
It will log in to Wattle and list possible courses to subscribe to. Enter the desired course numbers separated by spaces.
EchoDL will commence downloading all the lectures.


```
cp echodl.plist ~/Library/LaunchAgents
launchctl load ~/Library/LaunchAgents/echodl.plist
```
