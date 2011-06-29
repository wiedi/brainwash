#!/usr/bin/env python
import os, time
from os.path import *
from collections import defaultdict
from operator import itemgetter
import musicdns, musicdns.cache
from musicbrainz2.webservice import Query, TrackFilter, WebServiceError, ReleaseIncludes
from brainwash import myglob, formats_final, find_music_folders, filename_track_number, find_releases, MUSICDNS_KEY

def guess_release(folder, files):
	nfiles = []
	cache = musicdns.cache.MusicDNSCache()
	print "Fingerprinting..."
	for fn in files:
		try:
			puid, _ = cache.getpuid(fn, MUSICDNS_KEY)
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
			print u'	%d - %s - %s %s' % (tno, track.title, release.title, ' <=' if included else '')

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

	return releases


def decide_release(releases, nfiles):
	if not releases:
		return None
	for rel, freq in releases:
		print '========================'
		print 'MBID: %s'   % rel.id.split('/')[-1:][0]
		print 'Match:  %d' % freq
		print 'Title:  %s' % rel.title
		print 'Artist: %s' % rel.artist.name
		print ''
		for no, trk in enumerate(rel.tracks):
			print '	  %d. %s' % ((no+1), trk.title)

		if len(rel.getTracks()) != nfiles:
			print '/!\\ Unmatched number of tracks. /!\\'
		print ''

	if releases:
		maxfreq = max(freq for (rel, freq) in releases)
		mreleases = [rel for rel, freq in releases if freq == maxfreq]
		ntmatches = [rel for rel in mreleases if len(rel.getTracks()) == nfiles]
		chosen = ntmatches[0] if ntmatches else mreleases[0]

		if len(ntmatches) == 1:
			print '** Confidence High! **'

		# ask if guess is correct
		tmp_mbid = chosen.id.split('/')[-1:][0]
		print 'Selected %s' % tmp_mbid
		answer = raw_input('Correct? [Y|n]').strip()
		if answer == '' or answer.lower() == 'y':
			mbid = tmp_mbid
		else:
			print str(answer.lower())
			mbid = raw_input('Enter MBID: ').strip() or None
		chosen = mbid

	else:
		chosen = None

	return chosen


def main():
	musicdns.initialize()
	folders = find_music_folders('.')
	for folder in folders:
		music_files = myglob(folder[0], '*' + folder[1])
		try:
			mbid = file(folder[0] + '/.mbid').read().strip()
			print 'Skipped: ' + folder[0]
		except:
			print 'Found: ' + folder[0]
			mbid = decide_release(guess_release(folder[0], music_files), len(music_files))
			if mbid:
				file(folder[0] + '/.mbid', 'w').write(str(mbid))

if __name__ == '__main__':
	main()
