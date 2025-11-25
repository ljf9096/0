import re
import requests
import logging
from collections import OrderedDict
from datetime import datetime
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.FileHandler("function.log", "w", encoding="utf-8"), logging.StreamHandler()])

def parse_template(template_file):
    """解析模板文件，获取频道结构"""
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
    """从URL获取频道数据"""
    channels = OrderedDict()

    try:
        response = requests.get(url)
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

def filter_henan_sources(channel_urls):
    """河南联通的优质源，每个运营商最多保留4个"""
    henan_union_urls = []
    other_urls = []
    
    for url in channel_urls:
        elif 'ha.10010.cn' in url or 'henan.unicom' in url or '河南联通' in url:
            henan_union_urls.append(url)
        else:
            other_urls.append(url)
    
    # 每个运营商最多保留4个最好的源
    selected_urls = []
    selected_urls.extend(henan_union_urls[:4])   # 河南联通前4个
    
    # 如果河南源不足4个，用其他源补足
    if len(selected_urls) < 4:
        selected_urls.extend(other_urls[:4 - len(selected_urls)])
    
    return selected_urls[:4]  # 确保最多返回4个源

def match_channels(template_channels, all_channels):
    """匹配模板频道和在线频道，并筛选优质源"""
    matched_channels = OrderedDict()

    for category, channel_list in template_channels.items():
        matched_channels[category] = OrderedDict()
        for channel_name in channel_list:
            for online_category, online_channel_list in all_channels.items():
                for online_channel_name, online_channel_url in online_channel_list:
                    if channel_name == online_channel_name:
                        if channel_name not in matched_channels[category]:
                            matched_channels[category][channel_name] = []
                        matched_channels[category][channel_name].append(online_channel_url)

    # 对每个频道的URL进行筛选，保留最好的4个源
    for category in matched_channels:
        for channel_name in matched_channels[category]:
            urls = matched_channels[category][channel_name]
            matched_channels[category][channel_name] = filter_henan_sources(urls)

    return matched_channels

def filter_source_urls(template_file):
    """过滤源URL，获取匹配的频道"""
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
    """检查是否为IPv6地址"""
    return re.match(r'^http:\/\/\[[0-9a-fA-F:]+\]', url) is not None

def updateChannelUrlsM3U(channels, template_channels):
    """更新频道URL并生成M3U和TXT文件"""
    written_urls = set()

    with open("live.m3u", "w", encoding="utf-8") as f_m3u:
        f_m3u.write(f"""#EXTM3U x-tvg-url={",".join(f'"{epg_url}"' for epg_url in config.epg_urls)}\n""")

        with open("live.txt", "w", encoding="utf-8") as f_txt:
            # 直接写入频道数据，跳过公告部分
            for category, channel_list in template_channels.items():
                f_txt.write(f"{category},#genre#\n")
                if category in channels:
                    for channel_name in channel_list:
                        if channel_name in channels[category] and channels[category][channel_name]:
                            urls = channels[category][channel_name]
                            filtered_urls = []
                            
                            # 过滤黑名单URL和重复URL
                            for url in urls:
                                if url and url not in written_urls and not any(blacklist in url for blacklist in config.url_blacklist):
                                    filtered_urls.append(url)
                                    written_urls.add(url)
                            
                            # 为每个URL添加线路标识
                            total_urls = len(filtered_urls)
                            for index, url in enumerate(filtered_urls, start=1):
                                # 确定运营商类型
                                if 'ha.10086.cn' in url or 'henan.mobile' in url or '河南移动' in url:
                                    operator = "移动"
                                elif 'ha.10010.cn' in url or 'henan.unicom' in url or '河南联通' in url:
                                    operator = "联通"
                                else:
                                    operator = "其他"
                                
                                if is_ipv6(url):
                                    url_suffix = f"$LR•IPV6•{operator}" if total_urls == 1 else f"$LR•IPV6•{operator}『线路{index}』"
                                else:
                                    url_suffix = f"$LR•IPV4•{operator}" if total_urls == 1 else f"$LR•IPV4•{operator}『线路{index}』"
                                
                                if '$' in url:
                                    base_url = url.split('$', 1)[0]
                                else:
                                    base_url = url

                                new_url = f"{base_url}{url_suffix}"

                                f_m3u.write(f"#EXTINF:-1 tvg-id=\"{index}\" tvg-name=\"{channel_name}\" tvg-logo=\"https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/{channel_name}.png\" group-title=\"{category}\",{channel_name}\n")
                                f_m3u.write(new_url + "\n")
                                f_txt.write(f"{channel_name},{new_url}\n")

            f_txt.write("\n")
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    logging.info(f"文件生成完成，更新日期: {current_date}")

if __name__ == "__main__":
    template_file = "demo.txt"
    channels, template_channels = filter_source_urls(template_file)
    updateChannelUrlsM3U(channels, template_channels)
