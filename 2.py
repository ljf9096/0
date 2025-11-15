import re
import requests
import logging
import concurrent.futures
from collections import OrderedDict
from datetime import datetime
from typing import Dict, List, Tuple, Set
import config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("function.log", "w", encoding="utf-8"),
        logging.StreamHandler()
    ]
)


class ChannelProcessor:
    """频道处理器"""
    
    def __init__(self):
        self.written_urls: Set[str] = set()
    
    def parse_template(self, template_file: str) -> OrderedDict:
        """解析模板文件"""
        template_channels = OrderedDict()
        current_category = None

        try:
            with open(template_file, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    
                    if "#genre#" in line:
                        current_category = line.split(",")[0].strip()
                        template_channels[current_category] = []
                    elif current_category:
                        channel_name = line.split(",")[0].strip()
                        if channel_name:  # 确保频道名不为空
                            template_channels[current_category].append(channel_name)
            
            logging.info(f"模板文件 '{template_file}' 解析成功，共 {len(template_channels)} 个分类")
            return template_channels
            
        except FileNotFoundError:
            logging.error(f"模板文件 '{template_file}' 未找到")
            raise
        except Exception as e:
            logging.error(f"解析模板文件时出错: {e}")
            raise

    def fetch_channels(self, url: str) -> OrderedDict:
        """从URL获取频道数据"""
        channels = OrderedDict()

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            lines = response.text.splitlines()
            
            # 检测文件格式
            is_m3u = any("#EXTINF" in line for line in lines[:10])
            source_type = "m3u" if is_m3u else "txt"
            logging.info(f"URL: {url} 获取成功，格式: {source_type}")

            if is_m3u:
                self._parse_m3u_format(lines, channels)
            else:
                self._parse_txt_format(lines, channels)

            if channels:
                categories = ", ".join(channels.keys())
                logging.info(f"URL: {url} 解析成功✅，分类: {categories}")
            else:
                logging.warning(f"URL: {url} 未解析到任何频道数据")

        except requests.RequestException as e:
            logging.error(f"URL: {url} 获取失败❌, 错误: {e}")
        except Exception as e:
            logging.error(f"URL: {url} 解析失败❌, 错误: {e}")

        return channels

    def _parse_m3u_format(self, lines: List[str], channels: OrderedDict):
        """解析M3U格式"""
        current_category = None
        channel_name = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith("#EXTINF"):
                match = re.search(r'group-title="(.*?)",(.*)', line)
                if match:
                    current_category = match.group(1).strip()
                    channel_name = match.group(2).strip()
                    if current_category not in channels:
                        channels[current_category] = []
            elif line and not line.startswith("#") and current_category and channel_name:
                channel_url = line.strip()
                channels[current_category].append((channel_name, channel_url))
                channel_name = None  # 重置频道名

    def _parse_txt_format(self, lines: List[str], channels: OrderedDict):
        """解析TXT格式"""
        current_category = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if "#genre#" in line:
                current_category = line.split(",")[0].strip()
                channels[current_category] = []
            elif current_category and line:
                # 处理可能的格式：频道名,URL 或 只有频道名
                if "," in line:
                    parts = line.split(",", 1)
                    channel_name = parts[0].strip()
                    channel_url = parts[1].strip() if len(parts) > 1 else ''
                else:
                    channel_name = line
                    channel_url = ''
                
                if channel_name:
                    channels[current_category].append((channel_name, channel_url))

    def test_url_speed(self, url: str) -> float:
        """测试URL的响应速度（秒）"""
        try:
            # 清理URL，移除可能的路由参数
            clean_url = url.split('$')[0] if '$' in url else url
            
            start_time = datetime.now()
            response = requests.get(clean_url, timeout=5, stream=True)
            response.raise_for_status()
            # 只读取一小部分数据来测试速度
            for _ in response.iter_content(chunk_size=1024):
                break
            response.close()
            
            elapsed = (datetime.now() - start_time).total_seconds()
            logging.debug(f"URL速度测试: {clean_url} - {elapsed:.2f}秒")
            return elapsed
            
        except Exception as e:
            logging.debug(f"URL速度测试失败: {url} - {e}")
            return float('inf')  # 返回无限大表示失败

    def filter_fastest_urls(self, urls: List[str], max_urls: int = 3) -> List[str]:
        """筛选速度最快的前几个URL"""
        if not urls:
            return []
            
        # 如果URL数量少于等于最大限制，直接返回
        if len(urls) <= max_urls:
            return urls
            
        logging.info(f"测试 {len(urls)} 个URL的速度，保留最快的 {max_urls} 个")
        
        # 使用线程池并发测试速度
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # 创建URL到速度的映射
            future_to_url = {executor.submit(self.test_url_speed, url): url for url in urls}
            speed_results = {}
            
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    speed = future.result()
                    speed_results[url] = speed
                except Exception as e:
                    logging.warning(f"测试URL速度时出错 {url}: {e}")
                    speed_results[url] = float('inf')
        
        # 按速度排序（从小到大），取前max_urls个
        sorted_urls = sorted(speed_results.keys(), key=lambda x: speed_results[x])
        fastest_urls = sorted_urls[:max_urls]
        
        # 记录速度信息
        speed_info = []
        for url in fastest_urls:
            speed = speed_results[url]
            if speed == float('inf'):
                speed_info.append(f"{url}(失败)")
            else:
                speed_info.append(f"{url}({speed:.2f}s)")
        
        logging.info(f"速度最快的 {len(fastest_urls)} 个URL: {', '.join(speed_info)}")
        return fastest_urls

    def match_channels(self, template_channels: OrderedDict, all_channels: OrderedDict) -> OrderedDict:
        """匹配模板频道和在线频道"""
        matched_channels = OrderedDict()

        for category, channel_list in template_channels.items():
            matched_channels[category] = OrderedDict()
            for channel_name in channel_list:
                for online_category, online_channel_list in all_channels.items():
                    for online_channel_name, online_channel_url in online_channel_list:
                        if channel_name == online_channel_name and online_channel_url:
                            if channel_name not in matched_channels[category]:
                                matched_channels[category][channel_name] = []
                            matched_channels[category][channel_name].append(online_channel_url)
            
            # 记录匹配结果
            matched_count = len(matched_channels[category])
            logging.info(f"分类 '{category}': 模板频道 {len(channel_list)} 个, 匹配成功 {matched_count} 个")

        return matched_channels

    def filter_source_urls(self, template_file: str) -> Tuple[OrderedDict, OrderedDict]:
        """过滤源URL"""
        template_channels = self.parse_template(template_file)
        source_urls = config.source_urls

        all_channels = OrderedDict()
        for url in source_urls:
            fetched_channels = self.fetch_channels(url)
            for category, channel_list in fetched_channels.items():
                if category in all_channels:
                    all_channels[category].extend(channel_list)
                else:
                    all_channels[category] = channel_list

        matched_channels = self.match_channels(template_channels, all_channels)
        
        # 对每个频道的URL进行速度筛选，只保留最快的3个
        filtered_channels = OrderedDict()
        for category, channel_data in matched_channels.items():
            filtered_channels[category] = OrderedDict()
            for channel_name, urls in channel_data.items():
                # 筛选最快的3个URL
                fastest_urls = self.filter_fastest_urls(urls, max_urls=3)
                if fastest_urls:
                    filtered_channels[category][channel_name] = fastest_urls
                    logging.info(f"频道 '{channel_name}' 保留 {len(fastest_urls)} 个最快URL")
                else:
                    logging.warning(f"频道 '{channel_name}' 无可用URL")
        
        return filtered_channels, template_channels

    def is_ipv6(self, url: str) -> bool:
        """检查是否为IPv6地址"""
        return re.match(r'^https?://\[[0-9a-fA-F:]+\]', url) is not None

    def update_channel_urls_m3u(self, channels: OrderedDict, template_channels: OrderedDict):
        """更新频道URL并生成M3U和TXT文件"""
        self.written_urls.clear()

        # 更新公告日期
        current_date = datetime.now().strftime("%Y-%m-%d")
        for group in config.announcements:
            for announcement in group['entries']:
                if announcement.get('name') is None:
                    announcement['name'] = current_date

        try:
            with open("live.m3u", "w", encoding="utf-8") as f_m3u, \
                 open("live.txt", "w", encoding="utf-8") as f_txt:
                
                # 写入M3U头
                epg_urls_str = ",".join(f'"{epg_url}"' for epg_url in config.epg_urls)
                f_m3u.write(f"#EXTM3U x-tvg-url={epg_urls_str}\n")

                # 写入公告频道
                self._write_announcements(f_m3u, f_txt)
                
                # 写入普通频道
                self._write_regular_channels(f_m3u, f_txt, channels, template_channels)

            logging.info("频道文件生成成功: live.m3u, live.txt")

        except IOError as e:
            logging.error(f"写入文件失败: {e}")
            raise

    def _write_announcements(self, f_m3u, f_txt):
        """写入公告频道"""
        for group in config.announcements:
            f_txt.write(f"{group['channel']},#genre#\n")
            for announcement in group['entries']:
                name = announcement['name']
                logo = announcement.get('logo', '')
                url = announcement['url']
                
                f_m3u.write(f'#EXTINF:-1 tvg-id="1" tvg-name="{name}" tvg-logo="{logo}" group-title="{group["channel"]}",{name}\n')
                f_m3u.write(f"{url}\n")
                f_txt.write(f"{name},{url}\n")

    def _write_regular_channels(self, f_m3u, f_txt, channels: OrderedDict, template_channels: OrderedDict):
        """写入普通频道"""
        for category, channel_list in template_channels.items():
            f_txt.write(f"{category},#genre#\n")
            
            if category in channels:
                for channel_name in channel_list:
                    if channel_name in channels[category]:
                        self._write_channel_urls(f_m3u, f_txt, category, channel_name, channels[category][channel_name])
                    else:
                        logging.warning(f"频道未找到: {channel_name} (分类: {category})")

    def _write_channel_urls(self, f_m3u, f_txt, category: str, channel_name: str, urls: List[str]):
        """写入频道URL"""
        # 排序URL（IPv6优先或IPv4优先）
        ipv6_priority = config.ip_version_priority == "ipv6"
        sorted_urls = sorted(urls, key=lambda url: not self.is_ipv6(url) if ipv6_priority else self.is_ipv6(url))
        
        # 过滤URL
        filtered_urls = []
        for url in sorted_urls:
            if (url and url not in self.written_urls and 
                not any(blacklist in url for blacklist in config.url_blacklist)):
                filtered_urls.append(url)
                self.written_urls.add(url)

        if not filtered_urls:
            logging.warning(f"频道 '{channel_name}' 无可用URL")
            return

        # 写入URL
        total_urls = len(filtered_urls)
        for index, url in enumerate(filtered_urls, start=1):
            new_url = self._format_channel_url(url, total_urls, index)
            self._write_channel_entry(f_m3u, f_txt, category, channel_name, new_url, index)

    def _format_channel_url(self, url: str, total_urls: int, index: int) -> str:
        """格式化频道URL"""
        is_ipv6_url = self.is_ipv6(url)
        base_url = url.split('$', 1)[0] if '$' in url else url
        
        if total_urls == 1:
            suffix = "$LR•IPV6" if is_ipv6_url else "$LR•IPV4"
        else:
            suffix = f"$LR•IPV6『线路{index}』" if is_ipv6_url else f"$LR•IPV4『线路{index}』"
        
        return f"{base_url}{suffix}"

    def _write_channel_entry(self, f_m3u, f_txt, category: str, channel_name: str, url: str, index: int):
        """写入频道条目"""
        logo_url = f"https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/{channel_name}.png"
        
        # 写入M3U
        f_m3u.write(f'#EXTINF:-1 tvg-id="{index}" tvg-name="{channel_name}" tvg-logo="{logo_url}" group-title="{category}",{channel_name}\n')
        f_m3u.write(f"{url}\n")
        
        # 写入TXT
        f_txt.write(f"{channel_name},{url}\n")


def main():
    """主函数"""
    try:
        processor = ChannelProcessor()
        template_file = "demo.txt"
        
        channels, template_channels = processor.filter_source_urls(template_file)
        processor.update_channel_urls_m3u(channels, template_channels)
        
        logging.info("频道处理完成")
        
    except Exception as e:
        logging.error(f"程序执行失败: {e}")
        raise


if __name__ == "__main__":
    main()
