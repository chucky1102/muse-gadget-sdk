<!-- SPDX-License-Identifier: Apache-2.0 -->

# Spoken replies with a TTS server of your own

Muse gadgets get their replies as text and show them as captions (see
[#12](https://github.com/facebookincubator/muse-gadget-sdk/pull/12) and
[#14](https://github.com/facebookincubator/muse-gadget-sdk/issues/14)). This
fork adds a build option, `CONFIG_MUSE_LOCAL_TTS`, that speaks them: the
firmware sends each reply's text to an HTTP server you run and plays the MP3
that comes back, through the MP3 decoder and speaker path the SDK already has.
Captions still follow the speech.

[中文说明见文末](#中文说明)

## How it works

1. You hold the talk button and speak. The voice note goes to Muse as before.
2. Muse replies in text.
3. For each reply, the firmware POSTs the text to `CONFIG_MUSE_LOCAL_TTS_URL`.
   A background task reads the MP3 as it streams back, and the chat session
   task feeds it to `tts_data()`. That's the hook `start_tts()` in
   `components/muse/muse_chat_session.cpp` describes.
4. Playback starts as soon as the first MP3 frames arrive. With the server
   in this folder that was a little over a second after the reply's text.

With the speaker off (hold the speaker button on screen, or Settings >
Speaker), nothing is fetched and replies are captions only, as upstream.

## 1. Run the server

`server.py` here is about 50 lines: it checks a key, strips Markdown and URLs
from the text, and streams speech from Microsoft Edge's online voices through
the [`edge-tts`](https://github.com/rany2/edge-tts) package. `edge-tts` is an
unofficial client of that service. Any TTS that returns MP3 will do: see
[the protocol](#the-protocol) to write your own.

On a machine the gadget can reach:

```sh
mkdir -p /opt/muse-tts && cd /opt/muse-tts
cp /path/to/esp32/tools/muse/tts_server/server.py .
python3 -m venv .venv && .venv/bin/pip install edge-tts aiohttp

# Make up a key. The gadget sends it with every request.
umask 077
echo "MUSE_TTS_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')" > .env
# Optional: the voice (default en-US-AriaNeural) and port (default 8020).
# echo "MUSE_TTS_VOICE=zh-CN-XiaoxiaoNeural" >> .env

set -a; . ./.env; set +a
.venv/bin/python server.py
```

`edge-tts --list-voices` (in the venv) lists the voices. To keep the server
running, install [`muse-tts.service`](muse-tts.service) as a systemd unit, and
open the port in your firewall.

Check it from another machine:

```sh
curl -X POST -H "X-Key: YOUR_KEY" --data-binary "Hello from Muse." \
  http://YOUR_SERVER:8020/tts -o test.mp3
```

Without the key it answers 401.

## 2. Build the firmware

Build your board once as usual, then set these in that build directory's
`sdkconfig` (or under **Muse** in `idf.py menuconfig`) and build again:

```
CONFIG_MUSE_LOCAL_TTS=y
CONFIG_MUSE_LOCAL_TTS_URL="http://YOUR_SERVER:8020/tts"
CONFIG_MUSE_LOCAL_TTS_KEY="YOUR_KEY"
```

The build directory's `sdkconfig` is gitignored. Keep the URL and key there,
like the SDK token, and out of the `devices/sdkconfig.*` overlays.

The option needs `CONFIG_MUSE_HATCH` (a board with PSRAM and a speaker). It
has been tested on one board, the Waveshare ESP32-S3-Touch-AMOLED-2.16.

## The protocol

To use another TTS, serve this:

| | |
|---|---|
| Request | `POST` to the URL, body is the reply's text as UTF-8, `Content-Type: text/plain; charset=utf-8`, header `X-Key: <key>` |
| Response | `200`, body is MP3, streamed or whole. Mono or stereo at any sample rate: the firmware resamples to 16 kHz |
| Anything else | The reply isn't spoken |

The text is the reply as Muse wrote it, up to 4095 bytes, Markdown included,
so strip what shouldn't be read aloud.

## Notes

- **HTTP or HTTPS.** An `https://` URL is checked against the firmware's
  certificate bundle. Over plain `http://` the key and the replies cross the
  network in the clear.
- **ESP-IDF 6.0.1.** `vStreamBufferDeleteWithCaps()` in that release deletes
  the buffer with `vSemaphoreDelete()` and can free it twice
  ([espressif/esp-idf#18855](https://github.com/espressif/esp-idf/issues/18855)),
  which showed up here as a reboot now and then at the end of a reply. The
  fetch creates its stream buffer with `xStreamBufferCreateStatic()` instead.
- **Chinese.** Set `MUSE_TTS_VOICE=zh-CN-XiaoxiaoNeural` on the server. For
  Chinese captions, `CONFIG_MUSE_FONT_CJK=y` adds GB2312's 3755 level-1 hanzi
  to the 16 px text (about 130 KB, from GNU Unifont).

## Also in this fork

**Waveshare ESP32-S3-Touch-AMOLED-2.16** as a board with the full UI:

```sh
tools/muse/board.sh build s216
```

BOOT talks and PWR sleeps, as on the Waveshare 1.75. The overlay turns on
`CONFIG_MUSE_LOCAL_TTS` and `CONFIG_MUSE_FONT_CJK`; without a URL replies are
captions. Known issue: on battery, the screen and both buttons stopped
responding once after about ten hours while Wi-Fi and the Muse session ran on.
The cause isn't found yet.

## 中文说明

Muse 小设备的回复目前只有文字（官方已去掉语音回复）。这个分支加了一个编译选项
`CONFIG_MUSE_LOCAL_TTS`：固件把每条回复的文字发给你自己搭的 HTTP 服务，再把返回的
MP3 用 SDK 现成的解码和喇叭通路播出来，屏幕字幕照常显示。

1. **搭服务**：把本目录的 `server.py` 放到设备能访问的机器上，
   `pip install edge-tts aiohttp`，设置环境变量 `MUSE_TTS_KEY`（自己生成的随机密钥）
   后运行。说中文把 `MUSE_TTS_VOICE` 设成 `zh-CN-XiaoxiaoNeural`。长期运行用
   `muse-tts.service`。
2. **编译固件**：先正常编译一次，然后在该编译目录的 `sdkconfig` 里设置
   `CONFIG_MUSE_LOCAL_TTS=y`、`CONFIG_MUSE_LOCAL_TTS_URL`、`CONFIG_MUSE_LOCAL_TTS_KEY`，
   再编译、刷机。地址和密钥只写在编译目录里，不要提交。
3. **屏幕显示中文**：加 `CONFIG_MUSE_FONT_CJK=y`（3755 个常用汉字，约 130 KB）。

想换别的语音合成服务，按上面 [The protocol](#the-protocol) 一节实现同样的接口即可。
目前只在 Waveshare ESP32-S3-Touch-AMOLED-2.16 上测试过。
