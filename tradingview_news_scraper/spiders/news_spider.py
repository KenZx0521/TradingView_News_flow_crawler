# requirements.txt
# scrapy
# selenium
# webdriver-manager

import scrapy
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import json
import os
from datetime import datetime

class TradingViewNewsSpider(scrapy.Spider):
    name = 'tradingview_news'
    start_urls = ['https://www.tradingview.com/news-flow/?symbol=BINANCE:BTCUSDT']
    
    def __init__(self):
        # 設置Chrome選項
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # 無頭模式，如果需要看到瀏覽器運行請註釋掉
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # 初始化WebDriver
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        
        # XPATH路徑配置 - 請在此處填入您的XPATH
        self.xpaths = {
            'news_list': '//*[@id="news-screener-page"]/div/div/div/div[1]/div/div[2]/div[2]/div[2]/div',  # 新聞列表容器的XPATH
            'news_items': '//*[@id="news-screener-page"]/div/div/div/div[1]/div/div[2]/div[2]/div[2]/div/a',  # 新聞項目的XPATH（可點擊的連結）
            'right_panel': '//*[@id="news-screener-page"]/div/div/div/div[3]',  # 右側面板的XPATH
            'panel_title': '//*[@id="news-screener-page"]/div/div/div/div[3]/div/div/div/div/article/h2',  # 右側面板標題的XPATH
            'panel_content': '//*[@id="news-screener-page"]/div/div/div/div[3]/div/div/div/div/article/div[3]/div/div[1]/div[2]/span',  # 右側面板內容的XPATH
            'panel_symbols': '//*[@id="news-screener-page"]/div/div/div/div[3]/div/div/div/div/article/div[3]/div/div[1]/div[1]',  # 右側面板符號的XPATH
            'close_button': '',  # 關閉按鈕的XPATH（可選）
            'list_title': '//*[@id="news-screener-page"]/div/div/div/div[1]/div/div[2]/div[2]/div[2]/div/a[1]/article/div/div'  # 列表中標題的XPATH（相對於news_items）
        }
        
        # 初始化Markdown輸出
        self.markdown_content = []
        self.output_filename = f'tradingview_news_{datetime.now().strftime("%Y%m%d_%H%M%S")}.md'
        
    def parse(self, response):
        """主要解析函數"""
        self.driver.get(response.url)
        
        # 初始化Markdown文件標題
        self.markdown_content.append(f"# TradingView BTCUSDT 新聞報告\n")
        self.markdown_content.append(f"**爬取時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.markdown_content.append(f"**來源**: {response.url}\n\n")
        self.markdown_content.append("---\n\n")
        
        try:
            # 等待新聞列表加載
            if self.xpaths['news_list']:
                self.wait.until(EC.presence_of_element_located((By.XPATH, self.xpaths['news_list'])))
                self.logger.info("新聞列表加載完成")
            
            # 滾動頁面以加載更多新聞
            self.scroll_and_load_news()
            
            # 獲取所有新聞項目
            if not self.xpaths['news_items']:
                self.logger.error("請設置 news_items 的XPATH路徑")
                return
                
            news_items = self.driver.find_elements(By.XPATH, self.xpaths['news_items'])
            self.logger.info(f"找到 {len(news_items)} 條新聞")
            
            # 遍歷每個新聞項目
            for index, news_item in enumerate(news_items):
                try:
                    # 獲取新聞標題
                    title = self.get_news_title(news_item)
                    
                    # 點擊新聞項目
                    self.driver.execute_script("arguments[0].click();", news_item)
                    
                    # 等待右側面板加載
                    time.sleep(2)
                    
                    # 提取新聞詳細內容
                    news_data = self.extract_news_details(title, index)
                    
                    if news_data:
                        # 添加到Markdown內容
                        self.add_to_markdown(news_data)
                        yield news_data
                    
                    # 關閉右側面板
                    self.close_right_panel()
                    
                except Exception as e:
                    self.logger.error(f"處理第 {index+1} 條新聞時出錯: {str(e)}")
                    continue
                    
        except TimeoutException:
            self.logger.error("頁面加載超時")
        except Exception as e:
            self.logger.error(f"爬取過程中出錯: {str(e)}")
        
        # 保存Markdown文件
        self.save_markdown_file()
    
    def scroll_and_load_news(self):
        """滾動頁面加載更多新聞"""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_scrolls = 5  # 限制滾動次數
        
        while scroll_attempts < max_scrolls:
            # 滾動到頁面底部
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)  # 等待加載
            
            # 計算新的頁面高度
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                break
                
            last_height = new_height
            scroll_attempts += 1
            
        self.logger.info(f"完成 {scroll_attempts} 次滾動加載")
    
    def get_news_title(self, news_item):
        """獲取新聞標題"""
        try:
            if self.xpaths['list_title']:
                # 使用相對XPATH查找標題
                title_element = news_item.find_element(By.XPATH, self.xpaths['list_title'])
                title = title_element.text.strip()
                if title:
                    return title
            
            # 如果沒有設置XPATH或找不到，返回元素文本
            return news_item.text.strip() or "無標題"
            
        except Exception as e:
            self.logger.error(f"獲取標題時出錯: {str(e)}")
            return "無標題"
    
    def extract_news_details(self, title, index):
        """提取新聞詳細內容"""
        try:
            # 等待右側面板出現
            if not self.xpaths['right_panel']:
                self.logger.error("請設置 right_panel 的XPATH路徑")
                return None
                
            right_panel = self.wait.until(
                EC.presence_of_element_located((By.XPATH, self.xpaths['right_panel']))
            )
            
            # 提取標題（從右側面板）
            panel_title = self.extract_panel_title()
            
            # 提取內容
            content = self.extract_content()
            
            # 提取相關符號
            symbols = self.extract_symbols()
            
            news_data = {
                'index': index + 1,
                'list_title': title,  # 列表中的標題
                'panel_title': panel_title,  # 右側面板中的標題
                'content': content,
                'symbols': symbols,
                'url': self.driver.current_url
            }
            
            self.logger.info(f"成功提取第 {index+1} 條新聞: {panel_title[:50]}...")
            return news_data
            
        except TimeoutException:
            self.logger.error(f"第 {index+1} 條新聞右側面板加載超時")
            return None
        except Exception as e:
            self.logger.error(f"提取第 {index+1} 條新聞詳情時出錯: {str(e)}")
            return None
    
    def extract_panel_title(self):
        """從右側面板提取標題"""
        try:
            if self.xpaths['panel_title']:
                title_element = self.driver.find_element(By.XPATH, self.xpaths['panel_title'])
                return title_element.text.strip()
            else:
                self.logger.warning("未設置 panel_title 的XPATH路徑")
                return "無標題"
        except NoSuchElementException:
            self.logger.warning("使用XPATH未找到標題元素")
            return "無標題"
        except Exception as e:
            self.logger.error(f"提取面板標題時出錯: {str(e)}")
            return "無標題"
    
    def extract_content(self):
        """提取新聞內容"""
        try:
            if self.xpaths['panel_content']:
                # 支持單個或多個內容元素
                content_elements = self.driver.find_elements(By.XPATH, self.xpaths['panel_content'])
                
                contents = []
                for element in content_elements:
                    text = element.text.strip()
                    if text and len(text) > 10:  # 過濾掉太短的文本
                        contents.append(text)
                
                # 去重並合併內容
                unique_contents = list(dict.fromkeys(contents))  # 保持順序的去重
                return ' '.join(unique_contents) if unique_contents else "無內容"
            else:
                self.logger.warning("未設置 panel_content 的XPATH路徑")
                return "無內容"
                
        except Exception as e:
            self.logger.error(f"提取內容時出錯: {str(e)}")
            return "無內容"
    
    def extract_symbols(self):
        """提取相關符號"""
        try:
            if self.xpaths['panel_symbols']:
                symbol_elements = self.driver.find_elements(By.XPATH, self.xpaths['panel_symbols'])
                
                symbols = []
                for element in symbol_elements:
                    text = element.text.strip()
                    if text:
                        symbols.append(text)
                
                return list(set(symbols)) if symbols else []
            else:
                self.logger.warning("未設置 panel_symbols 的XPATH路徑")
                return []
                
        except Exception as e:
            self.logger.error(f"提取符號時出錯: {str(e)}")
            return []
    
    def close_right_panel(self):
        """關閉右側面板"""
        try:
            if self.xpaths['close_button']:
                # 使用設置的關閉按鈕XPATH
                close_btn = self.driver.find_element(By.XPATH, self.xpaths['close_button'])
                close_btn.click()
                time.sleep(1)
                return
            
            # 如果沒有設置關閉按鈕XPATH，點擊面板外部區域
            self.driver.execute_script("document.body.click();")
            time.sleep(1)
            
        except NoSuchElementException:
            # 如果找不到關閉按鈕，嘗試點擊頁面其他區域
            self.driver.execute_script("document.body.click();")
            time.sleep(1)
        except Exception as e:
            self.logger.error(f"關閉右側面板時出錯: {str(e)}")
    
    def add_to_markdown(self, news_data):
        """將新聞數據添加到Markdown內容中"""
        try:
            self.markdown_content.append(f"## {news_data['index']}. {news_data['panel_title']}\n\n")
            
            # 如果列表標題與面板標題不同，顯示列表標題
            if news_data['list_title'] != news_data['panel_title'] and news_data['list_title'] != "無標題":
                self.markdown_content.append(f"**列表標題**: {news_data['list_title']}\n\n")
            
            # 新聞內容
            if news_data['content'] and news_data['content'] != "無內容":
                self.markdown_content.append(f"**內容**:\n{news_data['content']}\n\n")
            
            # 相關符號
            if news_data['symbols']:
                symbols_text = ", ".join([f"`{symbol}`" for symbol in news_data['symbols']])
                self.markdown_content.append(f"**相關符號**: {symbols_text}\n\n")
            
            # 來源連結
            if news_data['url']:
                self.markdown_content.append(f"**來源**: [TradingView]({news_data['url']})\n\n")
            
            self.markdown_content.append("---\n\n")
            
        except Exception as e:
            self.logger.error(f"添加Markdown內容時出錯: {str(e)}")
    
    def save_markdown_file(self):
        """保存Markdown文件"""
        try:
            # 添加文件結尾
            self.markdown_content.append(f"\n---\n")
            self.markdown_content.append(f"**報告生成時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.markdown_content.append(f"**總共爬取**: {len([line for line in self.markdown_content if line.startswith('## ')])} 條新聞\n")
            
            # 寫入文件
            with open(self.output_filename, 'w', encoding='utf-8') as f:
                f.writelines(self.markdown_content)
            
            self.logger.info(f"Markdown文件已保存: {self.output_filename}")
            
        except Exception as e:
            self.logger.error(f"保存Markdown文件時出錯: {str(e)}")
    
    def closed(self, reason):
        """爬蟲結束時關閉瀏覽器"""
        self.driver.quit()
        self.logger.info("瀏覽器已關閉")
        self.logger.info(f"Markdown報告已保存至: {self.output_filename}")


# 運行腳本
if __name__ == "__main__":
    # 創建 Scrapy 設置
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings
    
    # 設置輸出格式 - 保留JSON作為備份
    settings = get_project_settings()
    settings.set('FEEDS', {
        'tradingview_news_backup.json': {
            'format': 'json',
            'encoding': 'utf8',
            'store_empty': False,
            'fields': ['index', 'list_title', 'panel_title', 'content', 'symbols', 'url'],
            'indent': 2
        }
    })
    
    # 設置用戶代理
    settings.set('USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    # 設置下載延遲
    settings.set('DOWNLOAD_DELAY', 2)
    settings.set('RANDOMIZE_DOWNLOAD_DELAY', True)
    
    # 創建爬蟲進程
    process = CrawlerProcess(settings)
    process.crawl(TradingViewNewsSpider)
    process.start()
    
    print(f"\n✅ 爬取完成！")
    print(f"📄 Markdown報告已保存")
    print(f"💾 JSON備份文件: tradingview_news_backup.json")