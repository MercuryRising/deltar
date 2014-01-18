import sys
import os
import subprocess
import logging
import time
import re

def find_and_add_new_files():
	'''
	Find files that are untracked by git
	'''
	command = ["git", "ls-files", "-o", "--full-name"]
	output = subprocess.check_output(command)
	newFiles = [f.strip() for f in output.splitlines() if f]
	if newFiles:
		print "New files to track: ", newFiles
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
		print "An ERROR OCCURRED!"
		#return None
	command = ["git", "commit", '''-m"%s"'''%message]
	commitStatus = subprocess.call(command)
	#print "Add status: %s Commit status: %s" %(addStatus, commitStatus)
	#if not addStatus and not commitStatus:
	#print filePath, " committed succesfully with message: ", message

def get_modified_lines(filePath):
	'''
	Given a filepath, will run git blame to determine what lines have been modified and uncommitted
		One of the modified lines will be used for the commit message.
		This only works for file additions, git blame does not output removed files.
	'''
	if os.path.isfile(filePath):
		added, removed, fileName = subprocess.check_output(["git", "diff", "--numstat", filePath]).split()
		
		if added == removed and added == "-":
			print "New binary file detected"
			commitMessage = "New binary file! This is probably not a good thing to add..."
		elif int(added):
			addedLines = get_added_lines(filePath)
			commitMessage = "ADD:"+"|".join( (l.strip() for l in addedLines) )[:50]+"..."
		elif int(removed):
			removedLines = get_removed_lines(filePath)
			commitMessage = "REM:"+"|".join( (l.strip() for l in removedLines) )[:50]+"..."
		
		#print "Committing %s with message %s" %(filePath, commitMessage)
		commit(filePath, commitMessage)
	else:
		print "Detected deleted file, removing from git -> ", filePath
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
		else:
			print "Exiting... please remove the directory from the list"
			exit()
	else:
		return "Good to go!"

def clean_directories(directories):
	'''
	Expand list of directories into full paths so user can use home shortcut
	'''
	return [os.path.expanduser(directory) for directory in directories]

def check_if_git_setup():
	command = ["git","config","--global","user.email"]
	output = subprocess.check_output(command)
	if not output:
		print "You need to setup your email and name with the following commands:"
		print "$ git config --global user.name your_name"
		print "$ git config --global user.email your_email_address"
		print "Do this and then run again."
		exit()

def push(branch="master"):
	command = ["git", "push", "origin", "master"]
	output = subprocess.check_output(command)


# Default directory will be the directory deltar.py is run from
# Change this to something else if you want, or just add target directories
defaultDir = os.path.abspath("./")
target_directories = [defaultDir]
target_directories = clean_directories(target_directories)

for d in target_directories:
	print d, check_if_git_repo(d)

print "Watching these directories: ", target_directories
time.sleep(2)

def run(target_directories, checkDelay=60, pushDelay=120):
	lastPush = time.time()
	dirty = True

	while True:
		for target_directory in target_directories:
			os.chdir(target_directory)
			deltas = subprocess.check_output(["git","ls-files","-mo"])
			if deltas:
				print "Changes since last commit:"
				print deltas.strip()
				find_and_commit_modified_files()
				find_and_add_new_files()
				dirty = True
			if not deltas and dirty:
				print target_directory, " - Up to date"
				if time.time() > lastPush+pushDelay:
					print "Pushing to master"
					push()
				dirty = False
		time.sleep(checkDelay)

run(target_directories)