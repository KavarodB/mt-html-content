import pandas as pd
import ast
from scrapper.web_scraper import WebScraper
import re

def clean_url_fragment(url):
    """Extract the core part of a URL for matching."""
    # Remove protocol
    url = url.replace('https://', '').replace('http://', '').replace('//', '')
    # Remove query parameters for matching
    url = url.split('?')[0]
    return url

def test_scraper_coverage():
    """
    Test if web_scraper returns HTML containing all actual URLs from article_test.csv
    """
    # Load test data - manually parse due to complex CSV format
    try:
        test_data = []
        with open('article_test.csv', 'r', encoding='utf-8') as f:
            lines = f.readlines()[1:]  # Skip header
            for line in lines:
                # Split only on first two commas to handle commas in the URL list
                parts = line.strip().split(',', 2)
                if len(parts) == 3:
                    domain, url, actual_urls_str = parts
                    test_data.append({
                        'domain': domain.strip(),
                        'url': url.strip(),
                        'actual_urls': actual_urls_str.strip()
                    })

        df = pd.DataFrame(test_data)
        print(f"Loaded {len(df)} test URLs from article_test.csv\n")
    except Exception as e:
        print(f"Error loading article_test.csv: {str(e)}")
        import traceback
        traceback.print_exc()
        return

    # Initialize scraper
    scraper = WebScraper()

    # Statistics
    total_articles = len(df)
    total_expected_urls = 0
    total_found_urls = 0
    articles_with_issues = []

    # Test each article
    for idx, row in df.iterrows():
        article_url = row['url']
        domain = row['domain']

        # Parse actual_urls (it's a string representation of a list)
        try:
            actual_urls_str = row['actual_urls'].strip()
            # Handle the list format
            actual_urls = ast.literal_eval(actual_urls_str)
            if not isinstance(actual_urls, list):
                actual_urls = [actual_urls]
        except Exception as e:
            print(f"[{idx+1}/{total_articles}] Error parsing actual_urls for {article_url}: {e}")
            continue

        # Flatten if urls contain srcset strings (multiple URLs in one string)
        expanded_urls = []
        for url in actual_urls:
            if isinstance(url, str):
                # Check if it's a srcset-like string with multiple URLs
                if ' ' in url and ('http' in url or '//' in url):
                    # Split by spaces and extract URLs
                    parts = url.split()
                    for part in parts:
                        if 'http' in part or part.startswith('//') or part.startswith('/'):
                            # Remove size descriptors
                            part = re.sub(r'\s+\d+w$', '', part)
                            expanded_urls.append(part)
                else:
                    expanded_urls.append(url)

        actual_urls = expanded_urls
        total_expected_urls += len(actual_urls)

        print(f"\n[{idx+1}/{total_articles}] Testing: {article_url}")
        print(f"  Domain: {domain}")
        print(f"  Expected {len(actual_urls)} URLs")

        # Scrape the article
        try:
            html_content = scraper.scrape(article_url)
            if not html_content:
                print("  ERROR: Failed to scrape content")
                articles_with_issues.append({
                    'url': article_url,
                    'issue': 'Failed to scrape',
                    'expected': len(actual_urls),
                    'found': 0
                })
                continue

            print(f"  Scraped HTML: {len(html_content)} chars")

            # Check if HTML contains img tags
            img_count = html_content.count('<img')
            iframe_count = html_content.count('<iframe')
            print(f"  Found {img_count} <img> tags and {iframe_count} <iframe> tags in HTML")

            # Check each actual URL
            found_count = 0
            missing_urls = []

            for actual_url in actual_urls:
                # Clean and prepare URL for matching
                search_url = clean_url_fragment(actual_url)

                # Check if URL appears in HTML
                # Try multiple patterns since URLs might be encoded or formatted differently
                found = False

                # Pattern 1: Direct substring match
                if actual_url in html_content:
                    found = True
                # Pattern 2: URL-decoded match
                elif search_url in html_content:
                    found = True
                # Pattern 3: Check for path-only match (for relative URLs)
                elif actual_url.startswith('/') and actual_url in html_content:
                    found = True
                # Pattern 4: Check without protocol
                elif actual_url.replace('https://', '').replace('http://', '') in html_content:
                    found = True

                if found:
                    found_count += 1
                    print(f"    [+] Found: {actual_url[:80]}...")
                else:
                    missing_urls.append(actual_url)
                    print(f"    [-] Missing: {actual_url[:80]}...")

            total_found_urls += found_count

            # Summary for this article
            coverage = (found_count / len(actual_urls) * 100) if actual_urls else 0
            print(f"  Coverage: {found_count}/{len(actual_urls)} ({coverage:.1f}%)")

            if missing_urls:
                articles_with_issues.append({
                    'url': article_url,
                    'issue': f'Missing {len(missing_urls)} URLs',
                    'expected': len(actual_urls),
                    'found': found_count,
                    'missing': missing_urls
                })

        except Exception as e:
            print(f"  ERROR: {str(e)}")
            articles_with_issues.append({
                'url': article_url,
                'issue': f'Exception: {str(e)}',
                'expected': len(actual_urls),
                'found': 0
            })

    # Final summary
    print(f"\n{'='*70}")
    print(f"FINAL RESULTS")
    print(f"{'='*70}")
    print(f"Articles tested: {total_articles}")
    print(f"Total expected URLs: {total_expected_urls}")
    print(f"Total found URLs: {total_found_urls}")
    overall_coverage = (total_found_urls / total_expected_urls * 100) if total_expected_urls else 0
    print(f"Overall coverage: {overall_coverage:.1f}%")
    print(f"Articles with issues: {len(articles_with_issues)}")

    if articles_with_issues:
        print(f"\n{'='*70}")
        print(f"ISSUES DETECTED:")
        print(f"{'='*70}")
        for issue in articles_with_issues:
            print(f"\nURL: {issue['url']}")
            print(f"  Issue: {issue['issue']}")
            print(f"  Expected: {issue['expected']}, Found: {issue['found']}")
            if 'missing' in issue and issue['missing']:
                print(f"  Missing URLs:")
                for missing in issue['missing'][:3]:  # Show first 3
                    print(f"    - {missing[:100]}...")

if __name__ == "__main__":
    test_scraper_coverage()
