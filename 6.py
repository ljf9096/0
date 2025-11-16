import re
import requests
import logging
from collections import OrderedDict
from datetime import datetime
from typing import Dict, List, Tuple, Set
import config
import time

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
        self.url_speed_cache: Dict[str, float] = {}
    
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
        """测试URL响应速度（毫秒）"""
        if url in self.url_speed_cache:
            return self.url_speed_cache[url]
            
        try:
            start_time = time.time()
            response = requests.head(url, timeout=5, allow_redirects=True)
            response_time = (time.time() - start_time) * 1000  # 转换为毫秒
            
            if response.status_code == 200:
                self.url_speed_cache[url] = response_time
                return response_time
            else:
                return float('inf')
        except:
            return float('inf')

    def is_henan_mobile_url(self, url: str) -> bool:
        """判断是否为河南移动源"""
        henan_mobile_keywords = [
            '移动', 'mobile', 'cmcc', '10086', 'yd',
            'ha.chinamobile', 'henanmobile'
        ]
        return any(keyword in url.lower() for keyword in henan_mobile_keywords)

    def is_henan_unicom_url(self, url: str) -> bool:
        """判断是否为河南联通源"""
        henan_unicom_keywords = [
            '联通', 'unicom', 'cucc', '10010', 'lt',
            'ha.chinaunicom', 'henanunicom'
        ]
        return any(keyword in url.lower() for keyword in henan_unicom_keywords)

    def categorize_and_sort_urls(self, urls: List[str]) -> List[str]:
        """对URL进行分类和排序"""
        # 分类
        henan_mobile_urls = []
        henan_unicom_urls = []
        other_urls = []
        
        for url in urls:
            if self.is_henan_mobile_url(url):
                henan_mobile_urls.append(url)
            elif self.is_henan_unicom_url(url):
                henan_unicom_urls.append(url)
            else:
                other_urls.append(url)
        
        # 测试速度并排序（速度快的在前）
        def sort_by_speed(url_list):
            speeds = [(url, self.test_url_speed(url)) for url in url_list]
            return [url for url, speed in sorted(speeds, key=lambda x: x[1])]
        
        sorted_mobile = sort_by_speed(henan_mobile_urls)
        sorted_unicom = sort_by_speed(henan_unicom_urls)
        sorted_other = sort_by_speed(other_urls)
        
        # 优先选择：河南移动2个 + 河南联通2个，如果不够则用其他源补足
        selected_urls = []
        selected_urls.extend(sorted_mobile[:2])  # 最快的前2个移动源
        selected_urls.extend(sorted_unicom[:2])  # 最快的前2个联通源
        
        # 如果移动+联通不足4个，用其他源补足
        if len(selected_urls) < 4:
            needed = 4 - len(selected_urls)
            selected_urls.extend(sorted_other[:needed])
        
        # 如果还是不足4个，用剩余的移动或联通源补足
        if len(selected_urls) < 4:
            remaining_mobile = sorted_mobile[2:] if len(sorted_mobile) > 2 else []
            remaining_unicom = sorted_unicom[2:] if len(sorted_unicom) > 2 else []
            
            all_remaining = remaining_mobile + remaining_unicom
            if all_remaining:
                # 对剩余源按速度排序
                remaining_speeds = [(url, self.test_url_speed(url)) for url in all_remaining]
                sorted_remaining = [url for url, speed in sorted(remaining_speeds, key=lambda x: x[1])]
                needed = 4 - len(selected_urls)
                selected_urls.extend(sorted_remaining[:needed])
        
        return selected_urls[:4]  # 确保最多返回4个

    def match_channels(self, template_channels: OrderedDict, all_channels: OrderedDict) -> OrderedDict:
        """匹配模板频道和在线频道"""
        matched_channels = OrderedDict()

        for category, channel_list in template_channels.items():
            matched_channels[category] = OrderedDict()
            for channel_name in channel_list:
                all_matched_urls = []
                for online_category, online_channel_list in all_channels.items():
                    for online_channel_name, online_channel_url in online_channel_list:
                        if channel_name == online_channel_name and online_channel_url:
                            all_matched_urls.append(online_channel_url)
                
                # 对匹配到的URL进行分类和排序
                if all_matched_urls:
                    selected_urls = self.categorize_and_sort_urls(all_matched_urls)
                    matched_channels[category][channel_name] = selected_urls
                    
                    # 记录详细的源信息
                    mobile_count = sum(1 for url in selected_urls if self.is_henan_mobile_url(url))
                    unicom_count = sum(1 for url in selected_urls if self.is_henan_unicom_url(url))
                    other_count = len(selected_urls) - mobile_count - unicom_count
                    
                    logging.info(f"频道 '{channel_name}': 选择 {len(selected_urls)} 个源 (移动:{mobile_count} 联通:{unicom_count} 其他:{other_count})")
            
            # 记录匹配结果
            matched_count = sum(len(urls) for urls in matched_channels[category].values())
            logging.info(f"分类 '{category}': 模板频道 {len(channel_list)} 个, 匹配成功 {matched_count} 个源")

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
        return matched_channels, template_channels

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
        # 过滤URL
        filtered_urls = []
        for url in urls:
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
        
        # 判断源类型
        if self.is_henan_mobile_url(url):
            provider = "移动"
        elif self.is_henan_unicom_url(url):
            provider = "联通"
        else:
            provider = "其他"
        
        if total_urls == 1:
            suffix = f"$LR•{provider}"
        else:
            suffix = f"$LR•{provider}『线路{index}』"
        
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
