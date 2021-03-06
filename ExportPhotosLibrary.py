#!/usr/bin/env python
# -*- coding: utf-8 -*-

#Based on:
#   https://github.com/samrushing/face_extractor
#   https://github.com/bdwilson/iPhotoDump


import sqlite3
import os
import sys
import shutil
import errno
import tempfile
import argparse
import signal
import filecmp

reload(sys)
sys.setdefaultencoding('utf8')


def bar(progress):
    i = progress/5
    sys.stdout.write('\r')
    sys.stdout.write("[%-20s] %d%%" % ('='*i, progress))
    sys.stdout.write('\r')
    sys.stdout.flush()


def clean_up():
    main_db.close()
    shutil.rmtree(tempDir)
    print "\nDeleted temporary files"


def make_sure_path_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise


def signal_handler(signal, frame):
        clean_up()
        sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

parser = argparse.ArgumentParser(description='Exports Photos Library to directory', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('-s', '--source', default="/Volumes/Transcend/Zdjęcia.photoslibrary", help='source, path to Photos.app library')
parser.add_argument('-d', '--destination', default="/Volumes/photo", help='destination, path to external directory')
parser.add_argument('-c', '--compare', default=False, help='compare files', action="store_true")
parser.add_argument('-n', '--dryrun', default=False, help='do not copy files', action="store_true")
group = parser.add_mutually_exclusive_group()
group.add_argument('-p', '--progress', help="show progress bar", default=True, action="store_true")
group.add_argument('-v', '--verbose', help="increase output verbosity", action="store_true")
args = parser.parse_args()

if args.verbose:
    args.progress = False
if args.progress:
    args.verbose = False

libraryRoot = args.source
destinationRoot = args.destination

if not os.path.isdir(destinationRoot):
    sys.stderr.write('destination is not a directory?\n')
    sys.exit(-1)

#copy database, we don't want to mess with original
tempDir = tempfile.mkdtemp()
databasePath = os.path.join(tempDir, 'Library.apdb')
databasePath2 = (databasePath,)
shutil.copyfile(os.path.join(libraryRoot, 'Database/Library.apdb'), databasePath)
#connect to database
main_db = sqlite3.connect(databasePath)
main_db.execute("attach database ? as L", databasePath2)

#cannot use one connection to do everything
connection1 = main_db.cursor()
images = 0

#count all images
for row in connection1.execute("select RKAlbum.modelid from L.RKAlbum where RKAlbum.albumSubclass=3"):
    albumNumber = (row[0],)
    connection2 = main_db.cursor()
    #get all photos in that album
    for row2 in connection2.execute("select RKAlbumVersion.VersionId from L.RKAlbumVersion where RKAlbumVersion.albumId = ?", albumNumber):
        versionId = (row2[0],)
        images += 1

print "Found "+str(images)+" images"

copied = 0
progress = 0
failed = 0

#find all "normal" albums
connection1 = main_db.cursor()
for row in connection1.execute("select RKAlbum.modelid, RKAlbum.name from L.RKAlbum where RKAlbum.albumSubclass=3"):
    albumNumber = (row[0],)
    albumName = row[1]
    if args.verbose:
        print albumName+":"
    connection2 = main_db.cursor()
    #get all photos in that album
    for row2 in connection2.execute("select RKAlbumVersion.VersionId from L.RKAlbumVersion where RKAlbumVersion.albumId = ?", albumNumber):
        versionId = (row2[0],)
        connection3 = main_db.cursor()
        #get image path/name
        for row in connection3.execute("select M.imagePath, V.fileName from L.RKVersion as V inner join L.RKMaster as M on V.masterUuid=M.uuid where V.modelId = ?", versionId):
            progress += 1
            if args.progress:
                bar(progress*100/images)
            imagePath = row[0]
            fileName = row[1]
            sourceImage = os.path.join(libraryRoot, "Masters", imagePath)
            destinationDirectory = os.path.join(destinationRoot, albumName)
            checkPath = os.path.join(destinationDirectory, fileName)
            if args.verbose:
                print "("+str(progress)+"/"+str(images)+") From:\t"+sourceImage+"\tto:\t"+checkPath
            make_sure_path_exists(destinationDirectory)
            if not os.path.isfile(checkPath):
                copied += 1
                if args.verbose:
                    print "Copying"
                if not args.dryrun:
                    try:
                        shutil.copy(sourceImage, destinationDirectory)
                    except IOError:
                        failed += 1
                        print "Failed to copy: %s. Skipping this element." % sourceImage
            else:
                if args.verbose:
                    print "File already exists"
                    if args.compare:
                        if args.verbose:
                            print "Comparing files"
                        if not filecmp.cmp(sourceImage, checkPath):
                            copied += 1
                            if not args.dryrun:
                                if args.verbose:
                                    print "Copying"
                                try:
                                    shutil.copy(sourceImage, destinationDirectory)
                                except IOError:
                                    failed += 1
                                    print "Failed to copy: %s. Skipping this element." % sourceImage

print "\nImages:\t"+str(images)+"\tcopied:\t"+str(copied)+"\tfailed:\t"+str(failed)

clean_up()
