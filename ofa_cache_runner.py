#!/usr/bin/env python
import os
import musicdns, musicdns.cache
from brainwash import formats_final, MUSICDNS_KEY



def find_files(root = '.', formats = formats_final):
	f = []
	for (path, dirs, files) in os.walk(root):
		f += [os.path.abspath(path) + '/' + file for file in files if file[-4:].lower() in formats]
        return f


def main():
	musicdns.initialize()
	cache = musicdns.cache.MusicDNSCache()
	for fn in find_files():
		print 'Fingerprinting: ' + os.path.relpath(fn)
		try:
			cache.getpuid(fn, MUSICDNS_KEY)
		except IOError:
			print 'Failed :/'

if __name__ == '__main__':
	main()
