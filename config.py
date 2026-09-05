# config.py
# IP版本优先级：ipv6 或 ipv4
ip_version_priority = "ipv6"

# 每个频道最多保留的链接数（按优先级排序后取前 N 个）
max_urls_per_channel = 4

# 需要爬取的直播源列表（支持 .m3u / .txt 格式）
source_urls = [
    "http://140.210.9.53:6789/L00001live.txt",
    "https://proxy.lalifeier.eu.org/https://raw.githubusercontent.com/RJZC-LRJ/RJ/caaf92ae6eb9214499e78c822d00df59dc7d7ddc/RJLIVE_V2.6.8/rj_live.m3u",
    "http://ok.html-5.me//i/%E6%B1%9F%E8%A5%BF%E7%9C%81%E9%B9%B0%E6%BD%AD%E5%B8%82%E7%94%B5%E4%BF%A1%E7%BB%84%E6%92%AD.txt",
    "https://proxy.lalifeier.eu.org/https://raw.githubusercontent.com/ljf9096/ds/main/y/y4",
    "https://proxy.lalifeier.eu.org/https://raw.githubusercontent.com/ljf9096/ds/main/y/y5",
    "https://proxy.lalifeier.eu.org/https://raw.githubusercontent.com/ljf9096/ds/main/y/y6",
    "https://proxy.lalifeier.eu.org/https://raw.githubusercontent.com/ljf9096/ds/main/y/y7",
    "https://proxy.lalifeier.eu.org/https://raw.githubusercontent.com/ljf9096/ds/main/y/y8",
    "https://proxy.lalifeier.eu.org/https://raw.githubusercontent.com/ljf9096/ds/main/y/y9",
    "https://iptv.catvod.com/tv.m3u",
    "https://gitee.com/lwr851/live/raw/master/iptv.m3u",
    "https://bc.188766.xyz/?ip=&mima=mianfeibuhuaqian&json=true",
    "https://gitee.com/zwssina/yunduanyuan/raw/master/SB",
    "https://d.kstore.dev/download/15366/6988.txt",
    "https://gh-proxy.com/https://github.com/Kimentanm/aptv/raw/master/m3u/iptv.m3u",
    "https://gitee.com/hw2837/iptv/raw/master/iptv",
    "https://ghproxy.net/https://raw.githubusercontent.com/wwb521/live/refs/heads/main/tv.m3u",
    "https://kkgithub.com/extdomains/cdn.jsdelivr.net/gh/ljf9096/ds/y/henanyidong.txt",
    "https://proxy.lalifeier.eu.org/https://raw.githubusercontent.com/Supprise0901/TVBox_live/main/live.txt",
    "https://proxy.lalifeier.eu.org/https://raw.githubusercontent.com/develop202/migu_video/refs/heads/main/interface.txt",
    "https://live.lizanyang.top/hn.m3u",
    "https://cdn.jsdelivr.net/gh/xuelong876/kodi@main/yd.m3u",
    "https://gitee.com/sy68/tv/raw/tv/zby",
    "https://proxy.lalifeier.eu.org/https://raw.githubusercontent.com/kakaxi-1/IPTV/main/iptv.txt",
    "https://proxy.lalifeier.eu.org/https://raw.githubusercontent.com/kakaxi-1/IPTV/main/ipv4.txt",
    "https://proxy.lalifeier.eu.org/https://raw.githubusercontent.com/liulei120/TVCrazy/main/output/itvlist.txt",
    "http://43.251.226.89:8080/live.txt",
    "https://proxy.lalifeier.eu.org/https://raw.githubusercontent.com/ioptu/IPTV.txt2m3u.player/main/migu.m3u",
    "https://ghproxy.net/https://raw.githubusercontent.com/develop202/migu_video/refs/heads/main/interface.txt"
]

# URL 黑名单（包含黑名单关键词的链接将被过滤）
url_blacklist = [
    "epg.pw/stream/",
    "103.40.13.71:12390",
    "[2409:8087:1a01:df::4077]/PLTV/",
    "8.210.140.75:68",
    "154.12.50.54",
    "yinhe.live_hls.zte.com",
    "8.137.59.151",
    "[2409:8087:7000:20:1000::22]:6060",
    "histar.zapi.us.kg",
    "www.tfiplaytv.vip",
    "dp.sxtv.top",
    "111.230.30.193",
    "148.135.93.213:81",
    "live.goodiptv.club",
    "iptv.luas.edu.cn",
    "[2409:8087:2001:20:2800:0:df6e:eb22]:80",
    "[2409:8087:2001:20:2800:0:df6e:eb23]:80",
    "[2409:8087:2001:20:2800:0:df6e:eb1d]/ott.mobaibox.com/",
    "[2409:8087:2001:20:2800:0:df6e:eb1d]:80",
    "[2409:8087:2001:20:2800:0:df6e:eb24]",
    "2409:8087:2001:20:2800:0:df6e:eb25]:80",
    "[2409:8087:2001:20:2800:0:df6e:eb27]"
]

# EPG 节目指南地址（用于生成 m3u 的 x-tvg-url）
epg_urls = [
    "https://live.fanmingming.com/e.xml",
    "http://epg.51zmt.top:8000/e.xml",
    "http://epg.aptvapp.com/xml",
    "https://epg.pw/xmltv/epg_CN.xml",
    "https://epg.pw/xmltv/epg_HK.xml",
    "https://epg.pw/xmltv/epg_TW.xml"
]

# 公告配置（若不需要公告，保持为空列表即可）
announcements = []
