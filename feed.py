from bs4 import BeautifulSoup
import re


def extract_posts_from_html(html_content):
    """
    Parses HTML content to extract image URLs, texts, and xcancel URLs.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # The articles are contained in divs with this specific class
    articles = soup.find_all('div', class_='article_magazine_content_wraper')
    
    extracted_data = []
    
    for article in articles:
        entry = {}
        
        # 1. Extract Xcancel URL
        # We look for the title link class
        title_link = article.find('a', class_='article_magazine_title_link')
        
        # If there is no title link, this might be a container div or header, so we skip
        if not title_link:
            continue
            
        entry['post_url'] = title_link.get('href')
        
        # 2. Extract Text
        title_div = article.find('div', class_='article_magazine_title')
        entry['text'] = title_div.get_text(strip=True) if title_div else "No text found"

        # 3. Extract Image URL
        # The image is hidden inside a style attribute: style="background-image:url('...')"
        img_div = article.find('div', class_='article_magazine_picture')
        entry['image_url'] = None
        
        if img_div and 'style' in img_div.attrs:
            style_attr = img_div['style']
            # Regex to capture the URL inside url('')
            # It handles single quotes, double quotes, or no quotes
            match = re.search(r"url\(['\"]?(.*?)['\"]?\)", style_attr)
            if match:
                entry['image_url'] = match.group(1)
        
        extracted_data.append(entry)
            
    return extracted_data