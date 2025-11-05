import os
import re
import hashlib
from datetime import datetime
from scraper.web_scraper import WebScraper

# Global variable: Load test URLs from csv file.
TEST_URLS = []

def load_test_urls():
    """
    Loads URLs from 'article_today.csv' into the global TEST_URLS list.
    Each item is a dictionary {'url': url}.
    """
    global TEST_URLS
    TEST_URLS = [] # Clear the list just in case

    try:
        with open('article_today.csv', 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
            # Skip header if it exists, otherwise process all lines. 
            # Assuming the first line is a header if there's more than one line.
            start_index = 1 if len(lines) > 1 and not lines[0].strip().startswith("http") else 0
            
            for line in lines[start_index:]:
                url = line.strip()
                if url: # Only add if the line is not empty
                    # Original code had 'parts = line.strip()' and 'url = parts'.
                    # Assuming each line contains only the URL.
                    TEST_URLS.append({'url': url})
        
        print(f"Loaded {len(TEST_URLS)} URLs from article_today.csv.")
        
    except FileNotFoundError:
        print("ERROR: 'article_today.csv' not found.")
    except Exception as e:
        print(f"ERROR loading URLs: {e}")

def test_article_extraction():
    """
    Test content_extractor.py (implied to be using WebScraper to get HTML) 
    on URLs from article_today.csv.
    Scrapes the HTML, saves it, and prints information.
    """
    # Load test URLs
    load_test_urls()

    if not TEST_URLS:
        print("INFO: No URLs to process. Exiting.")
        return

    # Create the output directory
    os.makedirs("scraped", exist_ok=True)

    scraper = WebScraper()
    print(f"\nTesting WebScraper on {len(TEST_URLS)} URLs.")
    print("=" * 65 + "\n")

    for idx, test_item in enumerate(TEST_URLS, 1):
        url = test_item['url']
        
        # Safely extract domain from URL
        domain_match = re.match(r"https?:\/{2}(?:www\.)?([^/]+)", url)
        if domain_match:
            domain = domain_match.group(1)
        else:
            domain = "unknown_domain"

        print(f"[{idx}/{len(TEST_URLS)}] Processing: {url[:60]}{'...' if len(url) > 60 else ''}")
        print(f"\nURL: {url}")
        
        try:
            # Scrape full HTML
            html = scraper.scrape(url)
            
            if not html:
                print("ERROR: Failed to scrape (returned empty HTML)\n")
                continue

            # Generate hash for the HTML content
            content_hash = hashlib.md5(html.encode('utf-8')).hexdigest()[:10]
            
            # Save scraped HTML to scrapped directory
            scrape_filename = f"{domain}_{content_hash}.html"
            scrape_path = os.path.join("scrapped", scrape_filename)
            
            with open(scrape_path, 'w', encoding='utf-8') as f:
                f.write(f"\n")
                f.write(f"\n")
                f.write(f"\n\n")
                f.write(html)

            print(f"Saved scraped HTML: {scrape_path}")
            print(f"Original HTML: {len(html)} chars\n")

        except Exception as e:
            print(f"\nERROR: {e}\n")

    print("=" * 80)
    print(f"DONE! Check the output directory: scrapped")
    print("=" * 80)


if __name__ == "__main__":
    test_article_extraction()