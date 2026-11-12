# 🎧 DJFufuMaster

This is my Discord music bot. I built it partly because I wanted one for my server, and partly as an excuse to learn how real apps get hosted and kept running.

Fair warning: it's a portfolio project, not something you can clone and run. Everything is set up for my own Oracle Cloud server, so you'd have to change a lot to get it working anywhere else.

## How it works

The bot is written in Python. It runs on a small Kubernetes setup (K3s) on one Oracle Cloud machine. It doesn't play the music itself. That job goes to a separate program called Lavalink, which runs next to the bot and streams the audio. Splitting things up this way keeps the bot fast, even when several people are queueing songs.

I can also see how it's doing. The bot reports a few stats about itself, and I chart them in Grafana, so I notice when something breaks before anyone in the server complains.

A couple of other details I spent more time on than I'd like to admit:

- When the bot can't join a voice channel (it's full, or the bot doesn't have permission), it tells you why instead of doing nothing.

- YouTube keeps changing how it blocks bots, so a small script refreshes the tokens the bot needs to keep playing audio.

- None of the passwords or tokens are in the code. They're stored on the server and handed to the bot when it starts.

## Where things are

.github/ the workflow that deploys the bot automatically
DJFufuMaster-Infra/ Terraform files that create the Oracle Cloud server
examples/ sample config files, so you can see what settings exist
k8s/ instructions telling Kubernetes how to run everything
scripts/bot/ the bot’s code (bot.py does most of the work)
scripts/pot/ the YouTube token refresh script
application.yml Lavalink’s settings
Dockerfile how the bot gets packaged
requirements.txt the Python libraries it needs

My real `.env` file with the actual secrets stays on my machine. Git is told to ignore it.

## Updating it

I don't log into the server to update anything. When I push to `main`, GitHub checks the code for mistakes, builds a fresh copy of the bot, sends the new files to the server and restarts the bot. The old version keeps running until the new one is ready, so the bot doesn't drop out of voice in the middle of a song.
