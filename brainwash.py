#!/usr/bin/python
# -*- coding: utf-8 -*-
__version__ = '0.9.8.0'

__howto__ = """

1. Abhängigkeiten:
==================

# python-musicdns
# python-musicbrainz2
# unp (recommends: unace, unrar, p7zip-full)
# mplayer
# lame
# vorbis-tools

# xml2dict


2. xml2dict:
============
wget http://xml2dict.googlecode.com/files/xml2dict-2008.6-tar.gz
tar zxf xml2dict-2008.6-tar.gz
sudo cp xml2dict-read-only/*.py /usr/local/lib/python2.6/dist-packages

"""

import os, sys, shutil, stat, time
import subprocess
import glob, re
from os.path import *
from collections import defaultdict
from operator import itemgetter
import urllib
import xml.etree.ElementTree as ET
from xml2dict import XML2Dict
import unicodedata
import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.oggvorbis import OggVorbis
from mutagen.flac import FLAC
import musicdns, musicdns.cache
from musicbrainz2.webservice import Query, TrackFilter, WebServiceError, ReleaseIncludes

formats = ['.mp3', '.ogg', 'flac', '.wma', '.ape', '.mpc', '.m4a', '.aac', '.wav', '.asf']
formats_final = ['.mp3', '.ogg', 'flac']

MUSICDNS_KEY = '0518f9d77a2492b52f8c8c5b24de5a0e'
LASTFM_KEY = 'dc1ddf536f0b0e56acdef49e3b66ca14'

def find_music_folders(root):
	"""Search all subdirs for music files. Returns a List of (path, filetype)s"""
	folders = []
	for (path, dirs, files) in os.walk(root):
		extensions = [file[-4:].lower() for file in files]
		filetypes = set(extensions).intersection(set(formats))
		if filetypes:
			folders += [[abspath(path), filetypes.pop()]]
	return folders

	


def filename_track_number(fn):
	"""Given filename, attempt to find the track numbers from the filenames."""
	try:
		if fn[-4:] == '.mp3':
			f = EasyID3(fn)
		elif fn[-4:] == '.ogg':
			f = OggVorbis(fn)
		elif fn[-4:] == 'flac':
			f = FLAC(fn)
		else:
			print 'Uh oh, no meta-file for ' + fn

		#tn = mutagen.File(fn).tags['TRCK'].text[0]
		tn = f['tracknumber'][0]
		if tn.find('/'):
			tn = int(tn.split('/')[0])
		else:
			tn = int(tn)
		if tn != 0:
			return tn
	except:
		pass
	mo = re.search('([0-9]+)', basename(fn))
	if mo:
		return int(mo.group(1)[-2:])


def find_releases(puid):
	"""
	Given a track's puid, return a list of
	(track-no, track, release)
	for each release that the song appeared on on.
	"""
	q = Query()
	f = TrackFilter(puid=puid)
	results = None
	while results == None:
		try:
			results = q.getTracks(f)
		except WebServiceError, e:
			print '!! WebServiceError: ', e
			print '!! Retry in 5 seconds...'
			time.sleep(5)

	out = []
	for r in results:
		track = r.track
		rels = track.getReleases()
		assert len(rels) == 1
		rel = rels[0]
		out.append((rel.getTracksOffset()+1, track, rel))
	return out
	
def myglob(folder, pattern):
	"""Return a possibly-empty list of files in folder that match pattern (case-insensitive)"""
	import fnmatch
	return [abspath(folder + '/' + f) for f in os.listdir(folder) if fnmatch.fnmatch(f.lower(), pattern)]


class BrainWash:
	def __init__(self, config):
		self.config = config
		self.musicdns_key = MUSICDNS_KEY
		musicdns.initialize()
		self.cache = musicdns.cache.MusicDNSCache()
		self.artist_tags = {}
		self.main()

	def guess_release(self, folder, files):
		nfiles = []
		print "Fingerprinting..."
		for fn in files:
			try:
				puid, _ = self.cache.getpuid(fn, self.musicdns_key)
			except IOError:
				puid = None
			track = filename_track_number(fn)
			nfiles += [(track, fn, puid)]
		nfiles.sort()
		
		matchrel = defaultdict(int)
		for i, (no, fn, puid) in enumerate(nfiles):
			print 'Asking MusicBrainz about ' + basename(fn)
			if puid is None:
				continue
			for tno, track, release in find_releases(puid):
				included = 0
				if no == tno:
					matchrel[release.id] += 1
					included = 1
				print u'    %d - %s - %s %s' % (tno, track.title, release.title, ' <=' if included else '')

		q = Query()
		i = ReleaseIncludes(
			artist=True,
			tracks=True,
			urlRelations=True
		)
		releaseids = sorted(matchrel.iteritems(), key=itemgetter(1), reverse=1)

		if not releaseids:
			return None

		releases = None
		while not releases:
			try:
				releases = [(q.getReleaseById(rid, i), freq) for rid, freq in releaseids]
			except WebServiceError, e:
				print '!! WebServiceError: ', e
				print '!! Retry in 5 seconds...'
				time.sleep(5)


		for rel, freq in releases:
			print '========================'
			print 'MBID: %s'   % rel.id.split('/')[-1:][0]
			print 'Match:  %d' % freq
			print 'Title:  %s' % rel.title
			print 'Artist: %s' % rel.artist.name
			print ''
			for no, trk in enumerate(rel.tracks):
				print '   %d. %s' % ((no+1), trk.title)
		
			if len(rel.getTracks()) != len(nfiles):
				print '/!\\ Unmatched number of tracks. /!\\'
			print ''
			
		if releases:
			maxfreq = max(freq for (rel, freq) in releases)
			mreleases = [rel for rel, freq in releases if freq == maxfreq]
			ntmatches = [rel for rel in mreleases if len(rel.getTracks()) == len(nfiles)]
			chosen = ntmatches[0] if ntmatches else mreleases[0]
		else:
			chosen = None

		return chosen


	def decode_to_wav(self, music_file):
		"""Decodes filename to wav. Returns the new filename."""
		file_wav = music_file[:-4] + '.wav'
		file_wav = file_wav.replace(',', '-')

		if music_file[-3:] == 'mpc' and subprocess.call(['which', 'mpc123'], stdout=subprocess.PIPE) == 0:
			subprocess.call([
				'mpc123', '--wav',
				file_wav, music_file])
			return file_wav

		subprocess.call([
			'mplayer',
			'-vc', 'null',
			'-vo', 'null',
			'-ao', 'pcm:fast:file=' + file_wav,
			music_file])
		return file_wav

	def encode_to_mp3(self, file_wav):
		"""Encodes a wav file to mp3. Returns the new filename"""
		file_mp3 = file_wav[:-3] + 'mp3'
		subprocess.call([
			'lame',
			'-V2',
			file_wav,
			file_mp3])
		return file_mp3

	def encode_to_ogg(self, file_wav):
		"""Encodes a wav file to ogg vorbis. Returns the new filename"""
		file_ogg = file_wav[:-3] + 'ogg'
		subprocess.call([
			'oggenc',
			file_wav,
			'-q',
			'7',
			'-o',
			file_ogg])
		return file_ogg

	def get_lastfm_tags(self, artist):
		"""
		Given an Artist, returns the top 3 last.fm tags
		"""
		url = """http://ws.audioscrobbler.com/2.0/?method=artist.gettoptags&artist=%s&api_key=%s"""
		
		if artist in self.artist_tags:
			return self.artist_tags[artist]
		try:
			url = url % (urllib.quote(artist), self.config['last_fm_api_key'])
			xml = XML2Dict()
			r = xml.fromstring(urllib.urlopen(url).read())
			s = ''
			i = 0
			for tag in r.lfm.toptags.tag:
				s += tag.name.capitalize()
				if i > 2:
					break
				s += ', '
				i += 1
			self.artist_tags[artist] = s
		except:
			s = ''
		return s
	
	def clean_filename(self, fn):
		"""
		strips bad chars
		"""
		return fn.replace('/', '-').replace(':', ' -')

	def main(self):
		if len(sys.argv) < 2:
			print "Usage:\n\t%s <archive|folder>" % sys.argv[0]
			sys.exit()

		s = os.path.abspath(sys.argv[1])
		try:
			shutil.rmtree('.brainwash-work')
		except:
			pass
		try:
			os.mkdir('.brainwash-work')
		except:
			pass
		os.chdir('.brainwash-work')
		
		if os.path.isdir(s):
			print 'Creating working copy...'
			shutil.copytree(s, 'work')
		else:
			subprocess.call(['unp', s])

		folders = find_music_folders('.')

		for folder in folders:
			music_files = myglob(folder[0], '*' + folder[1])
			if len(music_files) < 2:
				cue_files = myglob(folder[0], '*.cue')
				if len(cue_files) < 1:
					# ask for mbid
					# need to write cuesheet generation code!!!
					#print "There is no cue file. To generate one I need the Release MBID."
					#mbid = raw_input('Enter MBID: ').strip()
					print "There is no cuesheet. please generate one yourself :P"
					continue
				else:
					cue_file = cue_files[0]
				
				wav_file = self.decode_to_wav(music_files[0])
				subprocess.call([
						'bchunk',
						'-w',
						wav_file,
						cue_file,
						folder[0] + '/tmp-brainwash-'
						])
				wav_files = myglob(folder[0], 'tmp-brainwash-*.wav')
				music_files = []
				for wav_file in wav_files:
					music_files +=  [self.encode_to_mp3(wav_file)]
				folder[1] = '.mp3'
						
			# encode into a nice format
			if folder[1] not in formats_final:
				wav_files = []
				if folder[1] == '.wav':
					wav_files = music_files[:]
				else:
					for music_file in music_files:
						wav_files += [self.decode_to_wav(music_file)]
				music_files = []
				for wav_file in wav_files:
					music_files +=  [self.encode_to_mp3(wav_file)]
				folder[1] = '.mp3'
				# take over the tags?

			print 'Found: ' + folder[0]
			try:
				mbid = file(folder[0] + '/.mbid').read().strip()
				print 'Using existing mbid'
			except:
				release = self.guess_release(folder[0], music_files)
				if release is None:
					# ask for mbid
					print 'Could not guess!'
					mbid = raw_input('Enter MBID: ').strip()
				else:
					# ask if guess is correct
					tmp_mbid = release.id.split('/')[-1:][0]
					print 'Selected %s' % tmp_mbid
					answer = raw_input('Correct? [Y|n]').strip()
					if answer == '' or answer.lower() == 'y':
						mbid = tmp_mbid
					else:
						print str(answer.lower())
						mbid = raw_input('Enter MBID: ').strip()
 
				file(join(folder[0], '.mbid'), 'w').write(str(mbid))
			
			q = Query()
			i = ReleaseIncludes(
				artist=True,
				tracks=True,
				urlRelations=True,
				releaseEvents=True,
				discs=True				
			)
			try:
				release = q.getReleaseById(mbid, i)
			except WebServiceError, e:
				print 'Error: ', e
				continue
			
			dst = self.config['destination_dir']
			
			year = 9999
			
			for event in release.releaseEvents:
				year = min(year, int(event.date[:4]))
			
			if year == 9999:
				year = int(raw_input('Enter Release Year: ').strip())
			
			release_title = self.clean_filename(release.title)

			if release.TYPE_SOUNDTRACK in release.getTypes():
				dst += '/_soundtracks/(%s) %s/' % (year, release_title)
			elif not release.artist:
				dst += '/_va/(%s) %s/' % (year, release_title)
			else:
				sort_char = release.artist.sortName[:1].lower()
				sort_char = unicodedata.normalize('NFKD', sort_char).encode('ASCII', 'ignore')
				dst += '/%s/%s/(%s) %s/' % (
					sort_char,
					self.clean_filename(release.artist.sortName),
					year,
					release_title)			
			
			try:
				os.makedirs(dst)
			except:
				raw_input('Failed creating %s! Press Anykey' % dst)	
			file(join(dst, '.mbid'), 'w').write(str(mbid))
			
			for music_file in music_files:
				# fix permissions for broken archives
				os.chmod(music_file, (
					stat.S_IRUSR + 
					stat.S_IWUSR +
					stat.S_IRGRP +
					stat.S_IROTH))
				track_number = filename_track_number(music_file)
				track = release.tracks[track_number - 1]
				if folder[1] == '.mp3':
					#meta_file = MP3(music_file, ID3=EasyID3)
					meta_file = EasyID3()
				elif folder[1] == '.ogg':
					meta_file = OggVorbis(music_file)
				elif folder[1] == 'flac':
					meta_file = FLAC(music_file)
				else:
					print 'Uh oh, no meta-file for ' + music_file
				#if not meta_file.tags:
				#	meta_file.add_tags()
				artist = track.artist.name if track.artist else release.artist.name
				meta_file['title']       = track.title
				meta_file['artist']      = artist
				meta_file['album']       = release.title
				meta_file['tracknumber'] = str(track_number) + '/' + str(len(music_files))
				meta_file['genre']       = self.get_lastfm_tags(meta_file['artist'][0])
				meta_file.save(music_file)
				
				file_dst = dst + self.clean_filename('%02d-%s - %s%s%s' % (
					track_number,
					artist,
					track.title,
					'.' if folder[1] == 'flac' else '',
					folder[1]
				))
				os.rename(music_file, file_dst)

			# cover art
			image_files = myglob(folder[0], '*.[jpg|png]')
			if len(image_files) > 1:
				for image_file in image_files:
					os.rename(image_file, dst + basename(image_file))
			elif len(image_files) == 1:
				os.rename(image_files[0], dst + 'cover.' + image_files[0][-3:])
			else:
				# try downlaod from amazon
				if release.asin:
					urllib.urlretrieve(
						'http://images.amazon.com/images/P/' + release.asin + '.01.LZZZZZZZ.jpg',
						dst + 'cover.jpg'
						)
					if os.path.getsize(dst + 'cover.jpg') < 1000L:
						os.remove(dst + 'cover.jpg')
			print 'Done: ' + dst

		# clean up working copy
		os.chdir('..')
		shutil.rmtree('.brainwash-work')


if __name__ == '__main__':
	x = BrainWash({
		'last_fm_api_key': 'dc1ddf536f0b0e56acdef49e3b66ca14',
		'destination_dir': '/srv/audio/',
		'comment':         ''
	})
