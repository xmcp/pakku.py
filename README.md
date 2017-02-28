# 如果你使用Chrome浏览器，你可能更需要本程序的js版本，请移步 [pakku.js](https://github.com/xmcp/pakku.js)

![logo](https://cloud.githubusercontent.com/assets/6646473/17503651/20b41376-5e24-11e6-8829-6b8a0ccd47a9.png)
# Pakku
自动合并B站视频中相同的弹幕，让您免受节奏大师刷屏之苦

![screenshot](https://cloud.githubusercontent.com/assets/6646473/17503800/5cba26e8-5e25-11e6-87c1-04431ef58e17.png)

## Setup

1. `py -3 -m pip install -r requirements.txt`
2. `py -3 ./pakku.py`
3. 将代理设置成 `127.0.0.1:8887`
4. 愉快地看番

## 实现细节

所有时间差在7秒以内的、内容完全相同的弹幕会被合并。

合并之后的弹幕的模式（即顶部、滚动、底部）、颜色和大小与时间最早的弹幕相同。

另外，符合如下模式的弹幕将被视为相同：

- `^23{3,}$`
- `^6{4,}$`
- `^[fF]+$`
- `^[hH]+$`

## 为什么这么麻烦呢？

当我第一次要拿HTTP代理实现这个功能的时候，其实我是拒绝的，因为我知道这样的设计实在是太反人类了，用户一定会骂我。

<del>但我尝试用Chrome扩展实现，发现根本没有办法，因为Chrome扩展根本没法修改HTTP响应，重定向的话又会遇到一堆跨域的问题。</del>

**UPDATE: 在B站开始用HTML5播放器之后，我终于实现了用Chrome扩展实现pakku的夙愿~ 请移步 [pakku.js](https://github.com/xmcp/pakku.js)**
