import re
import requests
import logging
import time
from collections import OrderedDict
from datetime import datetime
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("function.log", "w", encoding="utf-8"),
                              logging.StreamHandler()])

def parse_template(template_file):
    template_channels = OrderedDict()
    current_category = None
    with open(template_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "#genre#" in line:
                    current_category = line.split(",")[0].strip()
                    template_channels[current_category] = []
                elif current_category:
                    channel_name = line.split(",")[0].strip()
                    template_channels[current_category].append(channel_name)
    return template_channels

def fetch_channels(url):
    channels = OrderedDict()
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        response.encoding = 'utf-8'
        lines = response.text.split("\n")
        current_category = None
        is_m3u = any("#EXTINF" in line for line in lines[:15])
        source_type = "m3u" if is_m3u else "txt"
        logging.info(f"url: {url} 获取成功，判断为{source_type}格式")

        if is_m3u:
            for line in lines:
                line = line.strip()
                if line.startswith("#EXTINF"):
                    match = re.search(r'group-title="(.*?)",(.*)', line)
                    if match:
                        current_category = match.group(1).strip()
                        channel_name = match.group(2).strip()
                        if current_category not in channels:
                            channels[current_category] = []
                elif line and not line.startswith("#"):
                    channel_url = line.strip()
                    if current_category and channel_name:
                        channels[current_category].append((channel_name, channel_url))
        else:
            for line in lines:
                line = line.strip()
                if "#genre#" in line:
                    current_category = line.split(",")[0].strip()
                    channels[current_category] = []
                elif current_category:
                    match = re.match(r"^(.*?),(.*?)$", line)
                    if match:
                        channel_name = match.group(1).strip()
                        channel_url = match.group(2).strip()
                        channels[current_category].append((channel_name, channel_url))
                    elif line:
                        channels[current_category].append((line, ''))
        if channels:
            categories = ", ".join(channels.keys())
            logging.info(f"url: {url} 爬取成功✅，包含频道分类: {categories}")
    except requests.RequestException as e:
        logging.error(f"url: {url} 爬取失败❌, Error: {e}")
    return channels

def match_channels(template_channels, all_channels):
    matched_channels = OrderedDict()
    for category, channel_list in template_channels.items():
        matched_channels[category] = OrderedDict()
        for channel_name in channel_list:
            for online_category, online_channel_list in all_channels.items():
                for online_channel_name, online_channel_url in online_channel_list:
                    if channel_name == online_channel_name:
                        matched_channels[category].setdefault(channel_name, []).append(online_channel_url)
    return matched_channels

def filter_source_urls(template_file):
    template_channels = parse_template(template_file)
    source_urls = config.source_urls
    all_channels = OrderedDict()
    for url in source_urls:
        fetched_channels = fetch_channels(url)
        for category, channel_list in fetched_channels.items():
            if category in all_channels:
                all_channels[category].extend(channel_list)
            else:
                all_channels[category] = channel_list
    matched_channels = match_channels(template_channels, all_channels)
    return matched_channels, template_channels

def is_ipv6(url):
    return re.match(r'^http:\/\/\[[0-9a-fA-F:]+\]', url) is not None

def validate_and_measure(url, timeout=5):
    """
    检测URL是否有效，并返回响应时间（秒）。
    返回 (is_valid, response_time)
    """
    if not url.startswith(('http://', 'https://')):
        # 非HTTP协议默认视为无效（无法用requests检测）
        return False, None

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        start = time.time()
        # 使用stream=True只获取头部，不下载完整内容（节省带宽）
        r = requests.get(url, timeout=timeout, stream=True, headers=headers, allow_redirects=True)
        elapsed = time.time() - start

        if r.status_code != 200:
            return False, None

        # 尝试读取前512字节，检查是否为错误页面（包含404/error等）
        try:
            chunk = r.raw.read(512)
        except:
            chunk = b''
        # 如果内容为空，视为无效
        if not chunk:
            return False, None
        # 检查是否包含常见错误关键词
        lower_chunk = chunk.lower()
        if b'404' in lower_chunk or b'error' in lower_chunk or b'not found' in lower_chunk:
            return False, None

        return True, elapsed
    except Exception as e:
        return False, None

def updateChannelUrlsM3U(channels, template_channels):
    written_urls = set()
    current_date = datetime.now().strftime("%Y-%m-%d")
    for group in config.announcements:
        for announcement in group['entries']:
            if announcement['name'] is None:
                announcement['name'] = current_date

    max_urls = getattr(config, 'max_urls_per_channel', 4)
    enable_validation = getattr(config, 'enable_validation', True)
    validation_timeout = getattr(config, 'validation_timeout', 5)

    with open("live.m3u", "w", encoding="utf-8") as f_m3u:
        f_m3u.write(f"""#EXTM3U x-tvg-url={",".join(f'"{epg_url}"' for epg_url in config.epg_urls)}\n""")

        with open("live.txt", "w", encoding="utf-8") as f_txt:
            # 写入公告
            for group in config.announcements:
                f_txt.write(f"{group['channel']},#genre#\n")
                for announcement in group['entries']:
                    f_m3u.write(f"""#EXTINF:-1 tvg-id="1" tvg-name="{announcement['name']}" tvg-logo="{announcement['logo']}" group-title="{group['channel']}",{announcement['name']}\n""")
                    f_m3u.write(f"{announcement['url']}\n")
                    f_txt.write(f"{announcement['name']},{announcement['url']}\n")

            # 处理模板频道
            for category, channel_list in template_channels.items():
                f_txt.write(f"{category},#genre#\n")
                if category not in channels:
                    continue

                for channel_name in channel_list:
                    if channel_name not in channels[category]:
                        continue

                    # 获取该频道的所有候选链接（去重、黑名单过滤）
                    raw_urls = channels[category][channel_name]
                    # 去重（基于url去重）
                    unique_urls = list(OrderedDict.fromkeys(raw_urls))
                    # 过滤黑名单
                    filtered_urls = []
                    for url in unique_urls:
                        if url and url not in written_urls:
                            if not any(blacklist in url for blacklist in config.url_blacklist):
                                filtered_urls.append(url)
                                written_urls.add(url)

                    if not filtered_urls:
                        continue

                    # ---- 有效性检测与测速 ----
                    valid_urls = []
                    if enable_validation:
                        logging.info(f"正在检测频道 '{channel_name}' 的 {len(filtered_urls)} 个链接...")
                        for url in filtered_urls:
                            is_valid, resp_time = validate_and_measure(url, timeout=validation_timeout)
                            if is_valid:
                                valid_urls.append((url, resp_time))
                            else:
                                logging.debug(f"无效链接: {url}")
                        # 按响应时间升序排序（速度最快在前）
                        valid_urls.sort(key=lambda x: x[1])
                        # 提取url列表
                        sorted_urls = [url for url, _ in valid_urls]
                    else:
                        # 不验证，沿用之前的IP版本优先级排序
                        sorted_urls = sorted(filtered_urls,
                                             key=lambda u: not is_ipv6(u) if config.ip_version_priority == "ipv6" else is_ipv6(u))

                    # 只取前 max_urls 个
                    final_urls = sorted_urls[:max_urls]
                    total_urls = len(final_urls)

                    # 写入文件
                    for index, url in enumerate(final_urls, start=1):
                        # 确定IP类型后缀
                        if is_ipv6(url):
                            suffix = f"$LR•IPV6" if total_urls == 1 else f"$LR•IPV6『线路{index}』"
                        else:
                            suffix = f"$LR•IPV4" if total_urls == 1 else f"$LR•IPV4『线路{index}』"
                        # 去除原URL可能已有的$后缀
                        base_url = url.split('$', 1)[0] if '$' in url else url
                        new_url = f"{base_url}{suffix}"

                        f_m3u.write(f"#EXTINF:-1 tvg-id=\"{index}\" tvg-name=\"{channel_name}\" tvg-logo=\"https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/{channel_name}.png\" group-title=\"{category}\",{channel_name}\n")
                        f_m3u.write(new_url + "\n")
                        f_txt.write(f"{channel_name},{new_url}\n")

            f_txt.write("\n")

if __name__ == "__main__":
    template_file = "demo.txt"
    channels, template_channels = filter_source_urls(template_file)
    updateChannelUrlsM3U(channels, template_channels)
