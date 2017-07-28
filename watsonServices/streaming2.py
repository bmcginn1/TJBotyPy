#!/usr/bin/env python

"""

                  888
                  888
                  888
88888b.   .d88b.  88888b.   .d88b.  888  888
888 "88b d88""88b 888 "88b d88""88b `Y8bd8P'
888  888 888  888 888  888 888  888   X88K
888  888 Y88..88P 888 d88P Y88..88P .d8""8b.     http://nobox.io
888  888  "Y88P"  88888P"   "Y88P"  888  888     http://github.com/noboxio


streaming2.py: rewrite of streaming.py

Author: Brandon Gong
Date: 7/28/17
"""

import sys
import ssl
import base64
import json
import threading
import time
import pyaudio
import websocket
from websocket._abnf import ABNF


class StreamingSTT:

    # Mic config.
    CHUNK = 16384
    FORMAT = pyaudio.paInt16
    # It is necessary to keep CHANNELS at 1. Streaming STT does not handle the
    # extra data well and returns unwanted hums.
    CHANNELS = 1
    RATE = 48000

    # RECSEC: how long to record speech.
    # TODO: integrate some speechrecorder.py code over here and get rid of this
    # variable.  Currently, recording stops after 5 seconds no matter if the
    # user is still talking or has stopped for a long time.
    RECSEC = 5

    # large array of json data returned by watson.
    FINAL = []

    # timeout
    TIMEOUT = None

    # the actual websocket

    WS = None

    # Constructor.  Basically all you really need is StreamingSTT(<username>,
    # <password>)
    def __init__(
            self,
            username,
            password,
            timeout=5,
            chunk=16384,
            format=pyaudio.paInt16,
            channels=1,
            rate=48000,
            recsec=5
    ):
        self.userpass = ":".join((username, password))
        self.TIMEOUT = timeout
        self.CHUNK = chunk
        self.FORMAT = format
        self.CHANNELS = channels
        self.RATE = rate
        self.RECSEC = recsec

    # read_audio starts a stream and sends chunks to watson realtime.
    def read_audio(self, ws, timeout):

        # get a stream
        p = pyaudio.PyAudio()
        stream = p.open(format=self.FORMAT,
                        channels=self.CHANNELS,
                        rate=self.RATE,
                        input=True,
                        frames_per_buffer=self.CHUNK)

        if __debug__:
            print("Starting recording")

        # magic happens here. Read a chunk from the stream, encode it as ABNF,
        # and put it through the websocket.
        # TODO: implement auto stop not hard-coded time
        for i in range(0, int(self.RATE / self.CHUNK * self.RECSEC)):
            data = stream.read(self.CHUNK)
            ws.send(data, ABNF.OPCODE_BINARY)

        # Disconnect the audio stream
        stream.stop_stream()
        stream.close()

        if __debug__:
            print("Done recording")

        # Get the final response from watson (waiting for 1 second to get it
        # back)
        data = {"action": "stop"}
        ws.send(json.dumps(data).encode('utf8'))
        time.sleep(1)

        # close the websocket
        ws.close()
        p.terminate()

    # this callback is used when the connection is activated.
    # basically initializing and configuring settings and stuff
    def on_open(self, ws):

        # dump this config dictionary out to JSON
        data = {
            "action": "start",
            "content-type": "audio/l16;rate=%d" % self.RATE,
            "continuous": True,
            "interim_results": True,
            "word_confidence": True,
            "timestamps": True,
            "max_alternatives": 3
        }

        # Send the dictionary through the socket.
        ws.send(json.dumps(data).encode('utf8'))

        # start a thread to read audio.
        threading.Thread(target=self.read_audio,
                         args=(ws, self.TIMEOUT)).start()

    # callback for when we receive a JSON message from watson.
    # egg: a useless parameter put there to avoid python yelling at me
    def on_message(self, egg, msg):

        # load json data into a multidimensional list
        data = json.loads(msg)

        # are there results?
        if "results" in data:

            # are those results final?
            if data["results"][0]["final"]:
                self.FINAL.append(data)

            if __debug__:
                # printing the many alternatives of what the user said
                print(data['results'][0]['alternatives'][0]['transcript'])

    # print those errors
    def on_error(self, error):
        if __debug__:
            print(error)

    # inform coder dude that websocket was closed
    def on_close(self, ws):
        if __debug__:
            print("Websocket closed.")

    # get_phrase should not be confused with read_audio.
    # get_phrase should always be called instead of read_audio.
    # it makes the necessary re-initializations and then calls read_audio
    # itself.
    def get_phrase(self):

        # empty out the finals list of the data from last use.

        self.FINAL = []

        # connect up the websocket
        headers = {}
        headers["Authorization"] = "Basic " + base64.b64encode(
            self.userpass.encode()).decode()
        url = ("wss://stream.watsonplatform.net//speech-to-text/api/v1/recognize"
               "?model=en-US_BroadbandModel")
        self.WS = websocket.WebSocketApp(url,
                                         header=headers,
                                         on_message=self.on_message,
                                         on_error=self.on_error,
                                         on_close=self.on_close)
        self.WS.on_open = self.on_open

        # run the websocket
        self.WS.run_forever(
            sslopt={
                "cert_reqs": ssl.CERT_NONE,
                "check_hostname": False,
                "ssl_version": ssl.PROTOCOL_TLSv1
            }
        )

        # return the parsed result
        return "".join([i['results'][0]['alternatives'][0]
                        ['transcript'] for i in self.FINAL])


if __name__ == "__main__":

    if len(sys.argv) < 3:
        print("Usage: " + sys.argv[0] + " <username> <password> [<timeout>]")
        sys.exit()

    elif len(sys.argv) > 3:
        StreamingSTT(sys.argv[1], sys.argv[2], sys.argv[3]).get_phrase()

    else:
        s = StreamingSTT(sys.argv[1], sys.argv[2])
        x = s.get_phrase()
        print(x)
        print("\n\n\n\nget_phrase can be called as much as you want.\n\n\n\n")
s.get_phrase()
