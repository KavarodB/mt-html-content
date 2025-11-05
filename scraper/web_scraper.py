from bs4 import BeautifulSoup
from bs4.element import Comment
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
from urllib.parse import urlparse

class WebScraper:
    def __init__(self):
        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        self.chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36')

    def scrape(self, url):
        """
        Fetch webpage content with dynamic content support and minimal parsing.

        Args:
            url (str): The URL to scrape

        Returns:
            str: Cleaned HTML with scripts and styles removed, or None on error
        """
        # Validate URL
        try:
            result = urlparse(url)
            if not result.scheme:
                raise ValueError("Invalid URL - missing scheme")
        except ValueError as e:
            print(f"Error: {e}")
            return None

        driver = None
        try:
            # Initialize WebDriver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=self.chrome_options)
            driver.set_page_load_timeout(30)

            # Execute CDP commands to prevent detection
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })

            # Load page
            driver.get(url)
            driver.implicitly_wait(5)

            # Scroll to load lazy content
            total_height = driver.execute_script("return document.body.scrollHeight")
            for i in range(0, total_height, 300):
                driver.execute_script(f"window.scrollTo(0, {i});")
                time.sleep(0.2)

            # Wait a bit more for any final dynamic content
            time.sleep(2)

            # Get the page source
            html_content = driver.page_source
            soup = BeautifulSoup(html_content, 'html.parser')

            # Remove scripts and styles
            for element in soup.find_all(['script', 'style']):
                element.decompose()

            # Remove comments
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()

            return str(soup)

        except Exception as e:
            print(f"Error scraping URL {url}: {str(e)}")
            return None

        finally:
            if driver:
                driver.quit()
