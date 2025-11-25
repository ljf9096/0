import re
import requests
import logging
from collections import OrderedDict
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("function.log", "w", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

def parse_template(template_file):
    """解析模板文件，获取频道结构"""
    template_channels = OrderedDict()
    current_category = None

    try:
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
        
        logging.info(f"模板文件解析成功，共找到 {len(template_channels)} 个分类")
        for category, channels in template_channels.items():
            logging.info(f"  {category}: {len(channels)} 个频道")
            
    except Exception as e:
        logging.error(f"解析模板文件失败: {e}")
    
    return template_channels

def fetch_channels(url):
    """从URL获取频道数据"""
    channels = OrderedDict()

    try:
        logging.info(f"开始获取URL: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        response.encoding = 'utf-8'
        lines = response.text.split("\n")
        
        current_category = None
        channel_name = None
        is_m3u = any("#EXTINF" in line for line in lines[:10])
        
        source_type = "m3u" if is_m3u else "txt"
        logging.info(f"URL: {url} 获取成功，判断为{source_type}格式")

        if is_m3u:
            # 处理M3U格式
            for i, line in enumerate(lines):
                line = line.strip()
                if line.startswith("#EXTINF"):
                    # 提取频道名称和分类
                    match = re.search(r'group-title="([^"]*)",([^$]*)', line)
                    if match:
                        current_category = match.group(1).strip()
                        channel_name = match.group(2).strip()
                        if not current_category:
                            current_category = "未分类"
                        
                        if current_category not in channels:
                            channels[current_category] = []
                    
                elif line and not line.startswith("#") and current_category and channel_name:
                    # 这是URL行
                    channel_url = line.strip()
                    channels[current_category].append((channel_name, channel_url))
                    channel_name = None  # 重置频道名称
                    
        else:
            # 处理TXT格式
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                if "#genre#" in line:
                    current_category = line.split(",")[0].strip()
                    channels[current_category] = []
                elif current_category and "," in line:
                    parts = line.split(",", 1)
                    if len(parts) == 2:
                        channel_name = parts[0].strip()
                        channel_url = parts[1].strip()
                        if channel_name and channel_url:
                            channels[current_category].append((channel_name, channel_url))

        # 统计结果
        total_channels = sum(len(channel_list) for channel_list in channels.values())
        logging.info(f"URL: {url} 爬取成功✅，共 {len(channels)} 个分类，{total_channels} 个频道")
        
    except requests.RequestException as e:
        logging.error(f"URL: {url} 爬取失败❌, Error: {e}")
    except Exception as e:
        logging.error(f"处理URL: {url} 时发生错误: {e}")

    return channels

def is_henan_unicom(url):
    """判断是否为河南联通源"""
    if not url:
        return False
    unicom_keywords = ['ha.10010.cn', 'henan.unicom', '河南联通', 'unicom', '联通']
    return any(keyword in url.lower() for keyword in unicom_keywords)

def filter_henan_unicom_sources(all_channels):
    """筛选所有频道的河南联通源，每个频道最多保留4个"""
    filtered_channels = OrderedDict()
    
    for category, channel_list in all_channels.items():
        filtered_channels[category] = OrderedDict()
        
        # 按频道名称分组
        channel_groups = {}
        for channel_name, channel_url in channel_list:
            if channel_name not in channel_groups:
                channel_groups[channel_name] = []
            channel_groups[channel_name].append(channel_url)
        
        # 对每个频道的URL进行筛选
        for channel_name, urls in channel_groups.items():
            # 筛选河南联通源
            henan_unicom_urls = [url for url in urls if is_henan_unicom(url)]
            # 取前4个
            selected_urls = henan_unicom_urls[:4]
            
            if selected_urls:
                filtered_channels[category][channel_name] = selected_urls
                logging.info(f"频道 {channel_name} 筛选到 {len(selected_urls)} 个河南联通源")
    
    return filtered_channels

def match_template_channels(template_channels, all_channels):
    """匹配模板频道和筛选后的频道数据"""
    matched_channels = OrderedDict()
    
    for category, template_channel_list in template_channels.items():
        matched_channels[category] = OrderedDict()
        
        for channel_name in template_channel_list:
            # 在所有分类中查找匹配的频道
            for online_category, online_channels in all_channels.items():
                if channel_name in online_channels:
                    if channel_name not in matched_channels[category]:
                        matched_channels[category][channel_name] = []
                    matched_channels[category][channel_name].extend(online_channels[channel_name])
                    break  # 找到一个匹配就跳出
    
    return matched_channels

def filter_source_urls(template_file, source_urls):
    """主过滤函数"""
    # 解析模板
    template_channels = parse_template(template_file)
    if not template_channels:
        logging.error("模板文件为空或解析失败")
        return OrderedDict(), template_channels
    
    # 获取所有源数据
    all_source_channels = OrderedDict()
    for url in source_urls:
        fetched_channels = fetch_channels(url)
        # 合并数据
        for category, channel_list in fetched_channels.items():
            if category not in all_source_channels:
                all_source_channels[category] = []
            all_source_channels[category].extend(channel_list)
    
    if not all_source_channels:
        logging.error("没有获取到任何频道数据")
        return OrderedDict(), template_channels
    
    # 筛选河南联通源
    filtered_channels = filter_henan_unicom_sources(all_source_channels)
    
    # 匹配模板频道
    matched_channels = match_template_channels(template_channels, filtered_channels)
    
    # 统计结果
    total_matched = sum(len(channels) for channels in matched_channels.values())
    logging.info(f"频道匹配完成，共匹配到 {total_matched} 个频道")
    
    return matched_channels, template_channels

def is_ipv6(url):
    """检查是否为IPv6地址"""
    return re.match(r'^http:\/\/\[[0-9a-fA-F:]+\]', url) is not None

def generate_output_files(channels, template_channels):
    """生成输出文件"""
    written_urls = set()
    
    try:
        with open("live.m3u", "w", encoding="utf-8") as f_m3u:
            f_m3u.write("#EXTM3U\n")
            
            with open("live.txt", "w", encoding="utf-8") as f_txt:
                # 遍历模板分类
                for category, channel_list in template_channels.items():
                    f_txt.write(f"{category},#genre#\n")
                    
                    if category in channels:
                        for channel_name in channel_list:
                            if channel_name in channels[category] and channels[category][channel_name]:
                                urls = channels[category][channel_name]
                                filtered_urls = []
                                
                                # 过滤重复URL
                                for url in urls:
                                    if url and url not in written_urls:
                                        filtered_urls.append(url)
                                        written_urls.add(url)
                                
                                # 生成输出
                                total_urls = len(filtered_urls)
                                for index, url in enumerate(filtered_urls, start=1):
                                    if is_ipv6(url):
                                        url_suffix = f"$LR•IPV6" if total_urls == 1 else f"$LR•IPV6『线路{index}』"
                                    else:
                                        url_suffix = f"$LR•IPV4" if total_urls == 1 else f"$LR•IPV4『线路{index}』"
                                    
                                    if '$' in url:
                                        base_url = url.split('$', 1)[0]
                                    else:
                                        base_url = url

                                    new_url = f"{base_url}{url_suffix}"

                                    # 写入M3U
                                    f_m3u.write(f'#EXTINF:-1 tvg-id="{index}" tvg-name="{channel_name}" tvg-logo="https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/{channel_name}.png" group-title="{category}",{channel_name}\n')
                                    f_m3u.write(f"{new_url}\n")
                                    
                                    # 写入TXT
                                    f_txt.write(f"{channel_name},{new_url}\n")
                
                f_txt.write("\n")
        
        logging.info(f"文件生成完成，共写入 {len(written_urls)} 个唯一URL")
        
    except Exception as e:
        logging.error(f"生成输出文件失败: {e}")

if __name__ == "__main__":
    # 配置源URL（示例，请根据实际情况修改）
    source_urls = [
        "http://example.com/playlist.m3u",  # 替换为实际的源URL
        "http://example.com/playlist.txt",   # 替换为实际的源URL
    ]
    
    template_file = "demo.txt"
    
    try:
        # 获取和过滤频道数据
        channels, template_channels = filter_source_urls(template_file, source_urls)
        
        if channels:
            # 生成输出文件
            generate_output_files(channels, template_channels)
            logging.info("处理完成！")
        else:
            logging.error("没有找到匹配的频道数据")
            
    except Exception as e:
        logging.error(f"程序执行失败: {e}")
