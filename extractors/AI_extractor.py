import re
from bs4 import BeautifulSoup, Comment
from openai import OpenAI

class LLMHtmlExtractor:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def _preclean_html(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")

        # Remove noisy elements
        for tag in soup(["script", "style", "noscript", "iframe", "header", "footer", "aside", "nav", "form"]):
            tag.decompose()

        # Remove entire <head>
        if soup.head:
            soup.head.decompose()

        # Remove inline CSS & JS attributes
        for tag in soup():
            if tag.attrs:
                tag.attrs = {k: v for k, v in tag.attrs.items() if k in ["src", "href"]}

        # Remove comments
        for c in soup.find_all(string=lambda text: isinstance(text, Comment)):
            c.extract()

        text = str(soup)

        # Remove weird whitespace
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def extract(self, html: str) -> str:
        cleaned = self._preclean_html(html)

        prompt = f"""
You are an HTML article cleaner.
Input HTML contains main content and noise like menus, ads, related posts, cookie banners, login prompts, and comments.

Rules:
- Return ONLY the main article content and its structure.
- KEEP: <h1>, <h2>, <h3>, <p>, <img>, <figure>, <figcaption>, <strong>, <em>, <ul>, <ol>, <li>, <blockquote>
- REMOVE: ads, related articles, menus, login, social media blocks, newsletter forms, comments, footers
- DO NOT add text. Do not invent content.
- DO NOT wrap inside <html> or <body>. Only return content container HTML.

Clean this HTML:\n\n
{cleaned}
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )

        return response.choices[0].message.content.strip()

