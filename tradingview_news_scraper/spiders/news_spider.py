import time

import scrapy
from scrapy.utils.project import get_project_settings
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
from dotenv import load_dotenv
import requests
from urllib.parse import urljoin, urlparse
from datetime import datetime

class TradingViewNewsSpider(scrapy.Spider):
    name = 'tradingview_news'
    start_urls = ['https://www.tradingview.com/accounts/signin/'] # Login頁面
    
    def __init__(self, *args, **kwargs):
        super(TradingViewNewsSpider, self).__init__(*args, **kwargs)
        # 設置Chrome選項
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        #chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument("--window-size=1200,8000")
        #chrome_options.add_argument("--start-fullscreen")
        chrome_options.add_argument("--force-device-scale-factor=0.1")
        
        # 初始化WebDriver
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        
        # XPATH路徑配置 - 請在此處填入您的XPATH
        self.xpaths = {
            # 登入頁面元素
            'email_button': '/html/body/div[3]/div/div/div[1]/div/div[2]/div[2]/div/div/button',  # Email登入按鈕
            'username_field': '//*[@id="id_username"]',  # 用戶名輸入框
            'password_field': '//*[@id="id_password"]',  # 密碼輸入框
            'login_button': '/html/body/div[3]/div/div/div[1]/div/div[2]/div[2]/div/div/div/form/button',  # 登入按鈕
            
            # 新聞頁面元素
            'news_list': '//*[@id="news-screener-page"]/div/div/div/div[1]/div/div[2]/div[2]/div[2]/div',  # 新聞列表容器的XPATH
            'news_items': '//*[@id="news-screener-page"]/div/div/div/div[1]/div/div[2]/div[2]/div[2]/div/a',  # 新聞項目的XPATH（可點擊的連結）
            'right_panel': '//*[@id="news-screener-page"]/div/div/div/div[3]',  # 右側面板的XPATH
            'panel_title': '//*[@id="news-screener-page"]/div/div/div/div[3]/div/div/div/div/article/h2',  # 右側面板標題的XPATH
            'panel_content': '//*[@id="news-screener-page"]/div/div/div/div[3]/div/div/div/div/article/div[3]/div/div[1]/div[2]/span',  # 右側面板內容的XPATH
            'panel_symbols': '//*[@id="news-screener-page"]/div/div/div/div[3]/div/div/div/div/article/div[3]/div/div[1]/div[1]',  # 右側面板符號的XPATH
            'close_button': '',  # 關閉按鈕的XPATH（可選）
            'list_title': '//*[@id="news-screener-page"]/div/div/div/div[1]/div/div[2]/div[2]/div[2]/div/a[1]/article/div/div'  # 列表中標題的XPATH（相對於news_items）
        }
        
        # 登入憑證 - 請設置您的登入資訊
        load_dotenv()
        self.credentials = {
            'username': os.getenv('USERNAME'),
            'password': os.getenv('PASSWORD')
        }
        
        

        # 初始化Markdown輸出
        self.markdown_content = []
        self.output_filename = f'tradingview_news_{datetime.now().strftime("%Y%m%d_%H%M%S")}.md'
        
        # 創建圖片保存目錄
        self.images_dir = f'images_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        os.makedirs(self.images_dir, exist_ok=True)
        
        # 圖片下載設置
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def parse(self, response):
        """主要解析函數 - 從登入頁面開始"""
        self.driver.get(response.url)
        
        try:
            # 執行自動登入
            if self.perform_login():
                self.logger.info("登入成功，導向新聞頁面")
                # 導向新聞頁面
                news_url = 'https://www.tradingview.com/news-flow/?symbol=BINANCE:BTCUSDT'
                self.driver.get(news_url)
                
                # 開始新聞爬取流程
                self.scrape_news()
            else:
                self.logger.error("登入失敗，無法繼續爬取")
                return
                
        except Exception as e:
            self.logger.error(f"爬取過程中出錯: {str(e)}")
        
        # 保存Markdown文件
        self.save_markdown_file()
    
    def perform_login(self):
        """執行自動登入"""
        try:
            self.logger.info("開始執行自動登入...")
            
            # 檢查登入憑證
            if not self.credentials['username'] or not self.credentials['password']:
                self.logger.error("請在 credentials 中設置用戶名和密碼")
                return False
            
            # 等待頁面加載
            time.sleep(1.5)
            
            # 1. 點擊Email登入按鈕
            email_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, self.xpaths['email_button']))
            )
            email_button.click()
            self.logger.info("已點擊Email登入按鈕")
            time.sleep(1)
            
            # 2. 填入用戶名
            username_field = self.wait.until(
                EC.presence_of_element_located((By.XPATH, self.xpaths['username_field']))
            )
            username_field.clear()
            username_field.send_keys(self.credentials['username'])
            self.logger.info("已填入用戶名")
            
            # 3. 填入密碼
            password_field = self.driver.find_element(By.XPATH, self.xpaths['password_field'])
            password_field.clear()
            password_field.send_keys(self.credentials['password'])
            self.logger.info("已填入密碼")
            
            # 4. 點擊登入按鈕
            login_button = self.driver.find_element(By.XPATH, self.xpaths['login_button'])
            login_button.click()
            self.logger.info("已點擊登入按鈕")
            
            # 等待登入完成 - 檢查是否跳轉到主頁面
            time.sleep(5)
            
            # 檢查是否登入成功（可以通過URL變化或特定元素來判斷）
            current_url = self.driver.current_url
            if 'signin' not in current_url:
                self.logger.info("登入成功！")
                return True
            else:
                self.logger.error("登入失敗，仍在登入頁面")
                return False
                
        except TimeoutException:
            self.logger.error("登入頁面元素加載超時")
            return False
        except Exception as e:
            self.logger.error(f"登入過程中出錯: {str(e)}")
            return False
    
    def scrape_news(self):
        """爬取新聞的主要流程"""
        # 初始化Markdown文件標題
        self.markdown_content.append(f"# TradingView BTCUSDT 新聞報告\n")
        self.markdown_content.append(f"**爬取時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.markdown_content.append(f"**來源**: {self.driver.current_url}\n\n")
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
                    time.sleep(0.5)
                    
                    # 提取新聞詳細內容
                    news_data = self.extract_news_details(title, index)
                    
                    if news_data:
                        # 添加到Markdown內容
                        self.add_to_markdown(news_data)
                        # 如果需要yield數據給Scrapy框架，可以在這裡添加
                    
                    # 關閉右側面板
                    self.close_right_panel()
                    
                except Exception as e:
                    self.logger.error(f"處理第 {index+1} 條新聞時出錯: {str(e)}")
                    continue
                    
        except TimeoutException:
            self.logger.error("新聞頁面加載超時")
        except Exception as e:
            self.logger.error(f"爬取新聞過程中出錯: {str(e)}")
    
    def scroll_and_load_news(self):
        """滾動頁面加載更多新聞"""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        while True:
            # 滾動到頁面底部
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)  # 等待加載
            
            # 計算新的頁面高度
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                break
                
            last_height = new_height
        
        self.logger.info("完成滾動加載")
    
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
            
            # 提取內容和圖片
            content_data = self.extract_content()
            
            # 提取相關符號
            symbols = self.extract_symbols()
            
            news_data = {
                'index': index + 1,
                'list_title': title,  # 列表中的標題
                'panel_title': panel_title,  # 右側面板中的標題
                'content': content_data['text'],  # 文本內容
                'images': content_data['images'],  # 圖片信息
                'symbols': symbols,
                'url': self.driver.current_url
            }
            
            self.logger.info(f"成功提取第 {index+1} 條新聞: {panel_title[:50]}... (包含 {len(content_data['images'])} 張圖片)")
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
        """提取新聞內容並下載圖片"""
        try:
            if self.xpaths['panel_content']:
                # 支持單個或多個內容元素
                content_elements = self.driver.find_elements(By.XPATH, self.xpaths['panel_content'])
                
                contents = []
                images = []
                
                for element in content_elements:
                    # 提取文本內容
                    text = element.text.strip()
                    if text and len(text) > 10:  # 過濾掉太短的文本
                        contents.append(text)
                    
                    # 查找並下載圖片
                    img_elements = element.find_elements(By.TAG_NAME, 'img')
                    for img in img_elements:
                        image_info = self.download_image(img)
                        if image_info:
                            images.append(image_info)
                
                # 去重並合併內容
                unique_contents = list(dict.fromkeys(contents))  # 保持順序的去重
                text_content = ' '.join(unique_contents) if unique_contents else "無內容"
                
                # 返回文本內容和圖片信息
                return {
                    'text': text_content,
                    'images': images
                }
            else:
                self.logger.warning("未設置 panel_content 的XPATH路徑")
                return {
                    'text': "無內容",
                    'images': []
                }
                
        except Exception as e:
            self.logger.error(f"提取內容時出錯: {str(e)}")
            return {
                'text': "無內容",
                'images': []
            }
    
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
                time.sleep(0.5)
                return
            
            # 如果沒有設置關閉按鈕XPATH，點擊面板外部區域
            self.driver.execute_script("document.body.click();")
            time.sleep(0.5)
            
        except NoSuchElementException:
            # 如果找不到關閉按鈕，嘗試點擊頁面其他區域
            self.driver.execute_script("document.body.click();")
            time.sleep(0.5)
        except Exception as e:
            self.logger.error(f"關閉右側面板時出錯: {str(e)}")
    
    def download_image(self, img_element):
        """下載圖片並返回圖片信息"""
        try:
            # 獲取圖片URL
            img_src = img_element.get_attribute('src')
            if not img_src:
                return None
            
            # 處理相對URL
            if img_src.startswith('//'):
                img_src = 'https:' + img_src
            elif img_src.startswith('/'):
                img_src = urljoin('https://www.tradingview.com', img_src)
            
            # 獲取圖片alt文本作為描述
            img_alt = img_element.get_attribute('alt') or 'image'
            
            # 生成文件名
            parsed_url = urlparse(img_src)
            file_extension = os.path.splitext(parsed_url.path)[1] or '.jpg'
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 毫秒級時間戳
            filename = f"image_{timestamp}{file_extension}"
            filepath = os.path.join(self.images_dir, filename)
            
            # 下載圖片
            response = self.session.get(img_src, timeout=10)
            response.raise_for_status()
            
            # 保存圖片
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            self.logger.info(f"圖片已下載: {filename}")
            
            return {
                'filename': filename,
                'filepath': filepath,
                'url': img_src,
                'alt': img_alt,
                'size': len(response.content)
            }
            
        except Exception as e:
            self.logger.error(f"下載圖片時出錯: {str(e)}")
            return None
    
    def add_to_markdown(self, news_data):
        """將新聞數據添加到Markdown內容中"""
        try:
            self.markdown_content.append(f"## {news_data['index']}. {news_data['panel_title']}\n\n")
            
            # 如果列表標題與面板標題不同，顯示列表標題
            if news_data['list_title'] != news_data['panel_title'] and news_data['list_title'] != "無標題":
                self.markdown_content.append(f"**Provider**: {news_data['list_title']}\n\n")
            
            # 新聞內容
            if news_data['content'] and news_data['content'] != "無內容":
                self.markdown_content.append(f"**內容**:\n{news_data['content']}\n\n")
            
            # 圖片（如果有）
            if news_data.get('images') and len(news_data['images']) > 0:
                self.markdown_content.append(f"**圖片** ({len(news_data['images'])} 張):\n\n")
                for i, img in enumerate(news_data['images'], 1):
                    # 添加圖片到Markdown
                    self.markdown_content.append(f"{i}. ![{img['alt']}]({img['filepath']})\n")
                    if img['alt'] and img['alt'] != 'image':
                        self.markdown_content.append(f"   - 描述: {img['alt']}\n")
                    self.markdown_content.append(f"   - 文件: `{img['filename']}`\n")
            
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
            # 計算總圖片數量
            total_images = sum([len(line.split('![')) - 1 for line in self.markdown_content if '![' in line])
            
            # 添加文件結尾
            self.markdown_content.append(f"\n---\n")
            self.markdown_content.append(f"**報告生成時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.markdown_content.append(f"**總共爬取**: {len([line for line in self.markdown_content if line.startswith('## ')])} 條新聞\n")
            self.markdown_content.append(f"**總共下載**: {total_images} 張圖片\n")
            self.markdown_content.append(f"**圖片保存目錄**: `{self.images_dir}/`\n")
            
            # 寫入文件
            with open(self.output_filename, 'w', encoding='utf-8') as f:
                f.writelines(self.markdown_content)
            
            self.logger.info(f"Markdown文件已保存: {self.output_filename}")
            
        except Exception as e:
            self.logger.error(f"保存Markdown文件時出錯: {str(e)}")
    
    def closed(self, reason):
        """爬蟲結束時關閉瀏覽器"""
        self.driver.quit()
        self.session.close()  # 關閉requests session
        self.logger.info("瀏覽器已關閉")
        self.logger.info(f"Markdown報告已保存至: {self.output_filename}")
        self.logger.info(f"圖片已保存至目錄: {self.images_dir}/")


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
            'fields': ['index', 'list_title', 'panel_title', 'content', 'images', 'symbols', 'url'],
            'indent': 2
        }
    })
    
    # 設置用戶代理
    settings.set('USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    # 設置下載延遲
    settings.set('DOWNLOAD_DELAY', 1)
    settings.set('RANDOMIZE_DOWNLOAD_DELAY', True)
    
    # 創建爬蟲進程
    process = CrawlerProcess(settings)
    process.crawl(TradingViewNewsSpider)
    process.start()
    
    print(f"\n✅ 爬取完成！")
    print(f"📄 Markdown報告已保存")
    print(f"🖼️ 圖片已保存至目錄")
    print(f"💾 JSON備份文件: tradingview_news_backup.json")