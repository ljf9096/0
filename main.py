import re
import requests
import logging
from collections import OrderedDict
from datetime import datetime
import config
import concurrent.futures
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.FileHandler("function.log", "w", encoding="utf-8"), logging.StreamHandler()])

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

def test_speed(url, timeout=3):
    """测试单个URL的响应速度"""
    try:
        start_time = time.time()
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        if response.status_code == 200:
            return time.time() - start_time
    except:
        pass
    return float('inf')  # 返回无穷大表示超时或失败

def filter_henan_unicom_urls(urls, max_urls=4):
    """筛选河南联通的URL并测试速度，保留最快的几个"""
    henan_unicom_urls = []
    other_urls = []
    
    # 分离河南联通和其他URL
    for url in urls:
        if 'henan' in url.lower() and 'unicom' in url.lower():
            henan_unicom_urls.append(url)
        else:
            other_urls.append(url)
    
    # 如果没有河南联通URL，直接返回空列表和其他URL
    if not henan_unicom_urls:
        return [], other_urls
    
    # 测试河南联通URL的速度
    logging.info(f"测试 {len(henan_unicom_urls)} 个河南联通URL的速度...")
    
    # 使用线程池并行测试速度
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(test_speed, url): url for url in henan_unicom_urls}
        speed_results = []
        
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                speed = future.result()
                speed_results.append((url, speed))
            except Exception as e:
                speed_results.append((url, float('inf')))
    
    # 按速度排序，取最快的max_urls个
    speed_results.sort(key=lambda x: x[1])
    fastest_henan_urls = [url for url, speed in speed_results[:max_urls] if speed < float('inf')]
    
    logging.info(f"保留最快的 {len(fastest_henan_urls)} 个河南联通URL")
    
    return fastest_henan_urls, other_urls

def updateChannelUrlsM3U(channels, template_channels):
    written_urls = set()

    with open("live.m3u", "w", encoding="utf-8") as f_m3u:
        # 检查config是否有epg_urls属性，如果没有就使用空列表
        epg_urls = getattr(config, 'epg_urls', [])
        if epg_urls:
            f_m3u.write(f"""#EXTM3U x-tvg-url={",".join(f'"{epg_url}"' for epg_url in epg_urls)}\n""")
        else:
            f_m3u.write("#EXTM3U\n")

        with open("live.txt", "w", encoding="utf-8") as f_txt:
            # 完全跳过公告部分，直接开始写入频道
            for category, channel_list in template_channels.items():
                f_txt.write(f"{category},#genre#\n")
                if category in channels:
                    for channel_name in channel_list:
                        if channel_name in channels[category]:
                            # 获取该频道的所有URL
                            all_urls = channels[category][channel_name]
                            
                            # 过滤黑名单URL
                            filtered_urls = [url for url in all_urls if url and url not in written_urls and not any(blacklist in url for blacklist in getattr(config, 'url_blacklist', []))]
                            
                            if not filtered_urls:
                                continue
                                
                            # 筛选河南联通URL，保留最快的4个
                            henan_unicom_urls, other_urls = filter_henan_unicom_urls(filtered_urls, max_urls=4)
                            
                            # 优先使用河南联通URL，如果没有则使用其他URL
                            final_urls = henan_unicom_urls if henan_unicom_urls else other_urls
                            
                            # 限制总URL数量，最多保留8个
                            final_urls = final_urls[:8]
                            
                            # 按IP版本排序
                            ip_version_priority = getattr(config, 'ip_version_priority', 'ipv4')
                            sorted_urls = sorted(final_urls, key=lambda url: not is_ipv6(url) if ip_version_priority == "ipv6" else is_ipv6(url))
                            
                            total_urls = len(sorted_urls)
                            for index, url in enumerate(sorted_urls, start=1):
                                if url in written_urls:
                                    continue
                                    
                                written_urls.add(url)
                                
                                # 判断是否为河南联通
                                is_henan_unicom = 'henan' in url.lower() and 'unicom' in url.lower()
                                
                                if is_ipv6(url):
                                    if is_henan_unicom:
                                        url_suffix = f"$LR•河南联通•IPV6" if total_urls == 1 else f"$LR•河南联通•IPV6『线路{index}』"
                                    else:
                                        url_suffix = f"$LR•IPV6" if total_urls == 1 else f"$LR•IPV6『线路{index}』"
                                else:
                                    if is_henan_unicom:
                                        url_suffix = f"$LR•河南联通•IPV4" if total_urls == 1 else f"$LR•河南联通•IPV4『线路{index}』"
                                    else:
                                        url_suffix = f"$LR•IPV4" if total_urls == 1 else f"$LR•IPV4『线路{index}』"
                                
                                if '$' in url:
                                    base_url = url.split('$', 1)[0]
                                else:
                                    base_url = url

                                new_url = f"{base_url}{url_suffix}"

                                f_m3u.write(f"#EXTINF:-1 tvg-id=\"{index}\" tvg-name=\"{channel_name}\" tvg-logo=\"https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/{channel_name}.png\" group-title=\"{category}\",{channel_name}\n")
                                f_m3u.write(new_url + "\n")
                                f_txt.write(f"{channel_name},{new_url}\n")

            f_txt.write("\n")

if __name__ == "__main__":
    template_file = "demo.txt"
    channels, template_channels = filter_source_urls(template_file)
    updateChannelUrlsM3U(channels, template_channels)
