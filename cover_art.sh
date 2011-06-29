#!/bin/bash
# last.fm cover fetcher
# version 0.2          
#

ALBUM_URL="http://ws.audioscrobbler.com/2.0/?method=album.getinfo&api_key=dc1ddf536f0b0e56acdef49e3b66ca14"

find . -name .mbid | while read mbid_file; do
        MBID=$(cat "$mbid_file")
        DIR=$(dirname "$mbid_file")
        echo $DIR : $MBID

        if test -n "$(find "$DIR" -maxdepth 1 -name 'cover.*' -print -quit)"; then
                echo 'cover already exists'
                continue
        fi

        URL="${ALBUM_URL}&mbid=$MBID"
        FILE=$(curl -s "$URL" | grep '<image size="extralarge">' | sed 's/ *<image size="extralarge">//' | sed 's/<\/image>//')

        if [ "${#FILE}" -eq "0" ]; then
                echo 'no cover found - *Di Dü*'
        else
                echo -n 'loading cover... '
                EXT=$(expr "$FILE" : '.*\(\..*\)')
                curl -s -L -o cover$EXT $FILE
                cp "cover$EXT" "$DIR/cover$EXT"
                echo 'all good'
        fi
done
