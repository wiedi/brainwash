#!/usr/bin/env python
import sys
from musicbrainz2.webservice import Query, TrackFilter, WebServiceError, ReleaseIncludes


def print_release(mbid):
	q = Query()
	i = ReleaseIncludes(
		artist=True,
		tracks=True,
		urlRelations=True
	)

	rel = q.getReleaseById(mbid, i)
	if not rel:
		print 'Not found :/'
		return

	print 'Title:  %s' % rel.title
	print 'Artist: %s' % rel.artist.name
	print ''
	for no, trk in enumerate(rel.tracks):
		print '	  %d. %s' % ((no+1), trk.title)


def main():
	if len(sys.argv) > 1:
		print_release(sys.argv[1])

if __name__ == '__main__':
	main()
