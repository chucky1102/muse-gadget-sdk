#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""A small TTS server for Muse gadgets built with CONFIG_MUSE_LOCAL_TTS.

    POST /tts   body: the reply's text (UTF-8)   header: X-Key: <your key>
    -> 200 audio/mpeg, streamed as it's synthesised

Speech comes from Microsoft Edge's online voices through the edge-tts package.
Set MUSE_TTS_KEY (required), and optionally MUSE_TTS_VOICE and PORT.
"""
import os
import re

import edge_tts
from aiohttp import web

KEY = os.environ["MUSE_TTS_KEY"]
VOICE = os.environ.get("MUSE_TTS_VOICE", "en-US-AriaNeural")
MAX_CHARS = 2000


def clean(text: str) -> str:
    """Drops what shouldn't be read aloud: code, URLs and Markdown marks."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)   # links and images: keep their text
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_`#>|~]+", "", text)
    text = re.sub(r"^\s*[-+]\s+", "", text, flags=re.M)      # list bullets
    return re.sub(r"\s+", " ", text).strip()[:MAX_CHARS]


async def tts(request: web.Request) -> web.StreamResponse:
    if request.headers.get("X-Key") != KEY:
        raise web.HTTPUnauthorized()
    text = clean(await request.text())
    if not text:
        raise web.HTTPBadRequest(text="empty")
    resp = web.StreamResponse(headers={"Content-Type": "audio/mpeg"})
    await resp.prepare(request)
    async for chunk in edge_tts.Communicate(text, VOICE).stream():
        if chunk["type"] == "audio":
            await resp.write(chunk["data"])
    await resp.write_eof()
    return resp


app = web.Application(client_max_size=64 * 1024)
app.router.add_post("/tts", tts)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8020")))
