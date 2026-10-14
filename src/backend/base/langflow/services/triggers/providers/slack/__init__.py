"""Slack as a trigger source (TRG-5).

One event model serves both Slack mechanisms. The Events API delivers a signed
HTTP POST to the app's Request URL (Track A, ``ingress.py``); Socket Mode
delivers the same body inside an envelope over a WebSocket the listener opens
(Track B, ``socket_mode.py``). Both hand the body to :func:`events.normalize`
and :func:`filters.matches`, so a flow sees identical Data whichever transport
carried the event, and a trigger can move between transports without a single
duplicate or missed run.
"""
