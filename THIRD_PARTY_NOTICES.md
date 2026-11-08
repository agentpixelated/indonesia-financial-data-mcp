# Third-Party Notices

## fzn0x/idx (ihsg-cli) — market-data backend

The optional market-data tools in `src/indonesia_data_mcp/market.py` invoke the
separately distributed `idx` binary from https://github.com/fzn0x/idx as a
subprocess. No upstream source code is copied into this repository; the binary
is obtained by the user via `npm install -g ihsg-cli`, `cargo install ihsg-cli`,
or the upstream install script. Attribution is provided voluntarily and in the
spirit of the upstream MIT License, whose full text is reproduced below.

Upstream project: https://github.com/fzn0x/idx

```
MIT License

Copyright (c) 2026 Midori Research and idx contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Note: the MIT License above covers the idx *software*. Market *data* returned
through it (Yahoo Finance / MSN Money / idx.co.id summaries) remains subject to
those data providers' own terms, is delayed, and is not official or licensed
IDX market data. This project labels every such response `official: false`.
