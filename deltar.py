import sys
import os
import stat
import subprocess
import time
import re
import logging

'''
deltar - automatically track changes as you work.

Will default to watch changes in the current working directory,
add new directories to targetDirectories to modify watched locations
'''
targetDirectories = [os.path.abspath("./")]

def find_and_add_new_files():
	'''
	Find files that are untracked by git
	'''
	command = ["git", "ls-files", "-o", "--full-name"]
	output = subprocess.check_output(command)
	newFiles = [f.strip() for f in output.splitlines() if f]
	if newFiles:
		logging.info(" Tracking the following new files: " + " ".join(newFiles))
		for newFile in newFiles:
			commit(newFile, "Adding new file %s"%newFile)

def find_and_commit_modified_files():
	'''
	Find the files that git determines have been modified
	'''	
	command = ["git", "ls-files", "-m", "--full-name"]
	output = subprocess.check_output(command)
	modifiedFiles = [f.strip() for f in output.splitlines() if f]
	#print modifiedFiles
	for modifiedFile in modifiedFiles:
		get_modified_lines(modifiedFile)

def commit(filePath, message):
	'''
	git commits filePath with message as commit message
	'''
	message = message.replace("!", "")
	command = ["git", "add", filePath]
	addStatus = subprocess.call(command)
	if addStatus:
		logging.error(" unable to add file %s!" %filePath)
	command = ["git", "commit", '''-m"%s"'''%message]
	commitStatus = subprocess.call(command)

def get_modified_lines(filePath):
	'''
	Given a filepath, will run git blame to determine what lines have been modified and uncommitted
		One of the modified lines will be used for the commit message.
		This only works for file additions, git blame does not output removed files.
	'''
	if os.path.isfile(filePath):
		added, removed, fileName = subprocess.check_output(["git", "diff", "--numstat", filePath]).split()
		
		if added == removed and added == "-":
			logging.log(" New binary file detected! This may not be a good thing to add...")
			commitMessage = "New binary file! This is probably not a good thing to add..."
		elif int(added):
			addedLines = get_added_lines(filePath)
			commitMessage = "|".join( (l.strip() for l in addedLines) )[:50]+"..."
		elif int(removed):
			removedLines = get_removed_lines(filePath)
			commitMessage = "REM:"+"|".join( (l.strip() for l in removedLines) )[:50]+"..."
		
		#print "Committing %s with message %s" %(filePath, commitMessage)
		commit(filePath, commitMessage)
		
	else:
		logging.info(" Detected deleted file, removing from git: " + filePath)
		subprocess.check_output(["git", "rm", filePath])

def get_added_lines(filePath, allLines=False):
	'''
	Find the lines that were added to the file filePath.
	'''
	#print "Finding added lines in", filePath
	command = ["git", "blame", filePath]
	output = subprocess.check_output(command)
	changes = re.findall("^(.*?) \((Not Committed Yet.*?)\) (.*)", output, re.MULTILINE)
	return [x[2] for x in changes if x[2]]

def get_removed_lines(filePath):
	'''
	Get lines that start with - or -- from git diff filePath
	'''
	output = subprocess.check_output(["git", "diff", "-U0", filePath])
	removedLines = re.findall(r"^\-{1,2}([^-].*?)\n", output, re.M)
	return removedLines

def init_repo(directory):
	'''
	Initialize directory as git repository
	'''
	os.chdir(directory)
	command = ["git", "init"]
	subprocess.call(command)

def check_if_git_repo(directory):
	'''
	Check if the specified directory is a git repository
	'''
	os.chdir(directory)
	command = ["git", "status"]
	returnCode = subprocess.call(command, stdout=subprocess.PIPE)
	if returnCode != 0:
		print "ERROR: return code: %s\nIs %s a git repo?\n" %(returnCode, directory)
		response = raw_input("Would you like to initialize this directory as a deltar directory? (y or n) >")
		if response == 'y':
			init_repo(directory)
			return True
		else:
			return False
	else:
		return True

def clean_directories(directories):
	'''
	Expand list of directories into full paths so user can use home shortcut
	'''
	return [os.path.expanduser(directory) for directory in directories]

def check_if_git_setup():
	command = ["git","config","--global","user.email"]
	output = subprocess.check_output(command)
	if not output:
		commands = ["$ git config --global user.name your_name", "$ git config --global user.email your_email_address"]
		commands = "\n".join(commands)
		logging.error(" git email or username not configured.")
		logging.info("Perform the following commands\n"+commands)
		logging.info(" Do this and then run deltar again.\nTerminating...")
		exit()

def push(branch="master"):
	'''
	Push to master, if there is an origin
	'''
	command = ["git", "push", "origin", branch]
	output = subprocess.check_output(command)

def has_remote(directory):
	'''
	Check if directory has remote
	'''
	command = ["git", "remote", "-v"]
	output = subprocess.check_output(command)
	if output: return True
	else: return False

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('deltar')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

targetDirectories = clean_directories(targetDirectories)
targetDirectories = [directory for directory in targetDirectories if check_if_git_repo(directory)]

logger.info(" Watching directories: " + " ".join(targetDirectories))

def run(targetDirectories, checkDelay=60, pushDelay=120):
	'''
	Run deltar on targetDirectories
	Wait checkDelay between checking files for changes
	Wait pushDelay between pushing to master
	'''
	directoryData = {directory:{"lastpush":time.time(), "lastdelta":os.stat(directory)[stat.ST_MTIME], "uptodate":False, "remind":False} for directory in targetDirectories}
	for tarDir in targetDirectories:
		directoryData[tarDir]['hasremote'] = has_remote(tarDir)
	while True:
		for targetDirectory in targetDirectories:
			os.chdir(targetDirectory)
			deltas = subprocess.check_output(["git","ls-files","-mo"])
			if deltas:
				logger.info(" Files Changed since last commit:")
				logger.info(deltas.strip())
				find_and_commit_modified_files()
				find_and_add_new_files()
				directoryData[targetDirectory]['uptodate'] = True
				directoryData[targetDirectory]['remind'] = True
				directoryData[targetDirectory]['lastdelta'] = time.time()

			if not deltas and directoryData[targetDirectory]['remind']:
				logger.info(" " +targetDirectory + " - Up to date")
				directoryData[targetDirectory]['remind'] = False

			if directoryData[targetDirectory]['hasremote']:
				if time.time() > directoryData[targetDirectory]['lastdelta'] + pushDelay:
					logging.info(" Pushing to %s master" %targetDirectory)
					push()
					directoryData[targetDirectory]['lastpush'] = time.time()
		time.sleep(checkDelay)

run(targetDirectories, 120, 5)